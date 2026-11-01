import base64
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core import services
from core.models import OrganizationMembership
from core.policy import ROLE_CAPABILITIES, Capability

Role = OrganizationMembership.Role


class IdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="owner", password="test-password")
        cls.other = get_user_model().objects.create_user(username="other", password="test-password")
        cls.organization = services.create_organization(owner=cls.owner, name="One")
        cls.foreign = services.create_organization(owner=cls.other, name="Other")
        cls.owner_membership = cls.organization.memberships.get(user=cls.owner)
        cls.foreign_membership = cls.foreign.memberships.get(user=cls.other)
        cls.users = {}
        cls.members = {}
        for role in [Role.ADMIN, Role.MANAGER, Role.AGENT]:
            user = get_user_model().objects.create_user(username=role, password="test-password")
            cls.users[role] = user
            cls.members[role] = services.add_member(
                actor=cls.owner, organization_id=cls.organization.pk, user_id=user.pk, role=role
            )

    def setUp(self):
        self.client = APIClient()
        self.login(self.owner)

    def login(self, user):
        credentials = base64.b64encode(f"{user.username}:test-password".encode()).decode()
        self.client.credentials(HTTP_AUTHORIZATION=f"Basic {credentials}")

    def org_url(self, organization=None):
        return f"/api/v1/organizations/{organization or self.organization.pk}/"

    def member_url(self, member, organization=None):
        return self.org_url(organization) + f"members/{member.pk}/"

    def test_real_authentication_and_safe_user_serialization(self):
        response = self.client.get("/api/v1/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"id", "username"})
        self.assertEqual(str(response.data["id"]), str(self.owner.pk))

    def test_anonymous_access_is_rejected(self):
        self.client.credentials()
        for url in [
            "/api/v1/users/me/",
            "/api/v1/organizations/",
            self.org_url(),
            self.org_url() + "members/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
        url = self.member_url(self.owner_membership)
        self.assertEqual(self.client.patch(url, {"role": Role.AGENT}).status_code, 401)
        self.assertEqual(self.client.delete(url).status_code, 401)
        self.assertEqual(self.client.post(self.org_url() + "members/", {}).status_code, 401)

    def test_bad_password_and_inactive_user_rejected(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Basic " + base64.b64encode(b"owner:wrong").decode()
        )
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 401)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.login(self.owner)
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 401)

    def test_multiple_organizations_are_scoped(self):
        second = services.create_organization(owner=self.owner, name="Two")
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {row["id"] for row in response.data["results"]},
            {str(self.organization.pk), str(second.pk)},
        )
        self.assertEqual(self.client.get(self.org_url(second.pk)).status_code, 200)

    def test_tenant_reads_do_not_disclose_existence(self):
        for suffix in ["", "members/"]:
            known = self.client.get(self.org_url(self.foreign.pk) + suffix)
            unknown = self.client.get(self.org_url(uuid.uuid4()) + suffix)
            self.assertEqual(known.status_code, 404)
            self.assertEqual(known.data, unknown.data)

    def test_cross_tenant_mutations_rejected(self):
        for organization in [self.organization.pk, self.foreign.pk]:
            url = self.member_url(self.foreign_membership, organization)
            self.assertEqual(self.client.patch(url, {"role": Role.AGENT}).status_code, 404)
            self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.org_url(self.foreign.pk) + "members/",
                {"user_id": str(self.owner.pk), "role": Role.OWNER},
            ).status_code,
            404,
        )
        self.foreign_membership.refresh_from_db()
        self.assertEqual(self.foreign_membership.role, Role.OWNER)

    def test_all_roles_read_only_authorized_members(self):
        for user in [self.owner, *self.users.values()]:
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(self.org_url()).status_code, 200)
                response = self.client.get(self.org_url() + "members/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data["results"]), 4)
                self.assertNotIn(
                    str(self.foreign_membership.pk), [row["id"] for row in response.data["results"]]
                )

    def test_role_capability_matrix(self):
        self.assertEqual(ROLE_CAPABILITIES[Role.OWNER], frozenset(Capability))
        self.assertEqual(ROLE_CAPABILITIES[Role.ADMIN], frozenset(Capability))
        for role in [Role.MANAGER, Role.AGENT]:
            self.assertEqual(
                ROLE_CAPABILITIES[role], {Capability.ORGANIZATION_VIEW, Capability.MEMBERS_VIEW}
            )

    def test_read_roles_cannot_mutate_or_escalate(self):
        for role in [Role.MANAGER, Role.AGENT]:
            self.login(self.users[role])
            self.assertEqual(
                self.client.patch(
                    self.member_url(self.members[role]), {"role": Role.OWNER}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.delete(self.member_url(self.members[Role.AGENT])).status_code, 403
            )
            self.assertEqual(
                self.client.post(
                    self.org_url() + "members/", {"user_id": str(self.other.pk), "role": Role.AGENT}
                ).status_code,
                403,
            )

    def test_admin_cannot_manage_or_grant_elevated_roles(self):
        self.login(self.users[Role.ADMIN])
        for member in [self.owner_membership, self.members[Role.ADMIN]]:
            self.assertEqual(
                self.client.patch(self.member_url(member), {"role": Role.AGENT}).status_code, 403
            )
            self.assertEqual(self.client.delete(self.member_url(member)).status_code, 403)
        for role in [Role.OWNER, Role.ADMIN]:
            self.assertEqual(
                self.client.patch(
                    self.member_url(self.members[Role.AGENT]), {"role": role}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(
                    self.org_url() + "members/", {"user_id": str(self.other.pk), "role": role}
                ).status_code,
                403,
            )

    def test_admin_can_manage_lower_roles(self):
        self.login(self.users[Role.ADMIN])
        response = self.client.patch(
            self.member_url(self.members[Role.AGENT]), {"role": Role.MANAGER}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], Role.MANAGER)
        response = self.client.post(
            self.org_url() + "members/", {"user_id": str(self.other.pk), "role": Role.AGENT}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.client.delete(self.member_url(self.members[Role.MANAGER])).status_code, 204
        )

    def test_final_owner_protected(self):
        url = self.member_url(self.owner_membership)
        self.assertEqual(self.client.patch(url, {"role": Role.ADMIN}).status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(self.client.patch(url, {"role": Role.OWNER}).status_code, 200)
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, Role.OWNER)

    def test_owner_transition_and_removal(self):
        response = self.client.patch(
            self.member_url(self.members[Role.ADMIN]), {"role": Role.OWNER}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.patch(
                self.member_url(self.owner_membership), {"role": Role.ADMIN}
            ).status_code,
            200,
        )
        self.login(self.users[Role.ADMIN])
        self.assertEqual(
            self.client.delete(self.member_url(self.owner_membership)).status_code, 204
        )
        self.assertEqual(self.organization.memberships.filter(role=Role.OWNER).count(), 1)

    def test_invalid_input_and_missing_identifiers(self):
        self.assertEqual(
            self.client.patch(
                self.member_url(self.members[Role.AGENT]), {"role": "SUPERUSER"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(self.member_url(self.members[Role.AGENT]), {}).status_code, 400
        )
        self.assertEqual(
            self.client.patch(
                self.org_url() + f"members/{uuid.uuid4()}/", {"role": Role.AGENT}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/v1/organizations/malformed/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/organizations/current/").status_code, 404)
        self.assertEqual(
            self.client.post(
                self.org_url() + "members/", {"user_id": "bad", "role": Role.AGENT}
            ).status_code,
            400,
        )

    def test_add_unknown_inactive_or_duplicate_account(self):
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        for user_id in [uuid.uuid4(), self.other.pk, self.owner.pk]:
            response = self.client.post(
                self.org_url() + "members/", {"user_id": str(user_id), "role": Role.AGENT}
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["user_id"], ["Cannot add this account."])

    def test_superuser_still_requires_organization_membership(self):
        self.other.is_superuser = True
        self.other.save(update_fields=["is_superuser"])
        self.login(self.other)
        self.assertEqual(self.client.get(self.org_url()).status_code, 404)
        self.assertEqual(
            self.client.patch(
                self.member_url(self.owner_membership), {"role": Role.AGENT}
            ).status_code,
            404,
        )

    def test_organization_creation_includes_owner_and_rejects_unsaved_user(self):
        organization = services.create_organization(owner=self.owner, name="New")
        member = organization.memberships.get()
        self.assertEqual(member.user_id, self.owner.pk)
        self.assertEqual(member.role, Role.OWNER)
        with self.assertRaises(ValidationError):
            services.create_organization(owner=get_user_model()(username="unsaved"), name="Invalid")

    def test_database_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationMembership.objects.create(
                organization=self.organization, user=self.owner, role=Role.AGENT
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationMembership.objects.filter(pk=self.owner_membership.pk).update(role="BAD")

    def test_user_deletion_cannot_cascade_membership(self):
        from django.db.models.deletion import ProtectedError

        with self.assertRaises(ProtectedError):
            self.owner.delete()

    def test_services_reject_invalid_role_and_nonmember_actor(self):
        with self.assertRaises(ValidationError):
            services.change_member_role(
                actor=self.owner,
                organization_id=self.organization.pk,
                membership_id=self.members[Role.AGENT].pk,
                role="BAD",
            )
        from django.http import Http404

        with self.assertRaises(Http404):
            services.remove_member(
                actor=self.other,
                organization_id=self.organization.pk,
                membership_id=self.members[Role.AGENT].pk,
            )


class OwnerConcurrencyTests(TransactionTestCase):
    def test_concurrent_owner_demotions_leave_an_owner(self):
        first = get_user_model().objects.create_user(username="first")
        second = get_user_model().objects.create_user(username="second")
        organization = services.create_organization(owner=first, name="Concurrent")
        one = organization.memberships.get(user=first)
        two = services.add_member(
            actor=first, organization_id=organization.pk, user_id=second.pk, role=Role.OWNER
        )
        barrier = Barrier(2)

        def demote(user, member):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                services.change_member_role(
                    actor=user,
                    organization_id=organization.pk,
                    membership_id=member.pk,
                    role=Role.ADMIN,
                )
                return "changed"
            except ValidationError:
                return "protected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(demote, first, one)
            b = pool.submit(demote, second, two)
            results = [a.result(timeout=20), b.result(timeout=20)]
        self.assertCountEqual(results, ["changed", "protected"])
        self.assertEqual(organization.memberships.filter(role=Role.OWNER).count(), 1)
