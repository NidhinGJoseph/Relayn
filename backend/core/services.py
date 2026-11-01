from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from core.models import Organization, OrganizationMembership
from core.policy import Capability, require_capability, require_role_authority
from core.tenancy import resolve_membership


def validate_role(role):
    if role not in OrganizationMembership.Role.values:
        raise ValidationError({"role": ["Invalid role."]})


@transaction.atomic
def create_organization(*, owner, name):
    if not owner.is_active or owner._state.adding:
        raise ValidationError("An active persisted owner is required.")
    organization = Organization(name=name)
    organization.full_clean()
    organization.save()
    OrganizationMembership.objects.create(
        organization=organization, user=owner, role=OrganizationMembership.Role.OWNER
    )
    return organization


def locked_actor(actor, organization_id):
    # Establish scope before locking; every mutation shares this organization lock.
    membership = resolve_membership(actor, organization_id)
    get_object_or_404(
        Organization.objects.select_for_update(of=("self",)).filter(memberships__user=actor),
        pk=membership.organization_id,
    )
    # A competing mutation may have changed or removed this actor while we waited.
    return resolve_membership(actor, organization_id)


@transaction.atomic
def add_member(*, actor, organization_id, user_id, role):
    membership = locked_actor(actor, organization_id)
    require_capability(membership, Capability.MEMBERS_CREATE)
    validate_role(role)
    require_role_authority(membership, role)
    # No user search/list API: an operator must already know the account UUID.
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise ValidationError({"user_id": ["Cannot add this account."]})
    if OrganizationMembership.objects.filter(
        organization=membership.organization, user=user
    ).exists():
        raise ValidationError({"user_id": ["Cannot add this account."]})
    return OrganizationMembership.objects.create(
        organization=membership.organization, user=user, role=role
    )


def mutation_target(membership, membership_id, capability):
    require_capability(membership, capability)
    target = get_object_or_404(
        OrganizationMembership.objects.filter(organization=membership.organization),
        pk=membership_id,
    )
    require_role_authority(membership, target.role)
    return target


def protect_last_owner(target):
    if target.role == OrganizationMembership.Role.OWNER and not (
        OrganizationMembership.objects.filter(
            organization=target.organization, role=OrganizationMembership.Role.OWNER
        )
        .exclude(pk=target.pk)
        .exists()
    ):
        raise ValidationError({"role": ["The final owner cannot be demoted or removed."]})


@transaction.atomic
def change_member_role(*, actor, organization_id, membership_id, role):
    membership = locked_actor(actor, organization_id)
    target = mutation_target(membership, membership_id, Capability.MEMBERS_CHANGE_ROLE)
    validate_role(role)
    require_role_authority(membership, role)
    if target.role != role:
        protect_last_owner(target)
        target.role = role
        target.save(update_fields=["role", "updated_at"])
    return target


@transaction.atomic
def remove_member(*, actor, organization_id, membership_id):
    membership = locked_actor(actor, organization_id)
    target = mutation_target(membership, membership_id, Capability.MEMBERS_REMOVE)
    protect_last_owner(target)
    target.delete()
