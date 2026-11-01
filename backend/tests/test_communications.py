import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import IntegrityError, close_old_connections, transaction
from django.http import Http404
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from billing.definitions import Capability
from billing.services import set_capability
from channels.models import Channel, ChannelAccount
from communications import services
from communications.models import Contact, ContactIdentity, Conversation, Message
from core.models import Organization, OrganizationMembership, User


class CommunicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="One")
        cls.other = Organization.objects.create(name="Other")
        cls.user = User.objects.create_user(username="agent")
        OrganizationMembership.objects.create(organization=cls.org, user=cls.user, role="AGENT")
        set_capability(cls.org, Capability.SHARED_INBOX, enabled=True)
        cls.channel, _ = Channel.objects.get_or_create(code="WHATSAPP")
        cls.account = ChannelAccount.objects.create(organization=cls.org, channel=cls.channel)
        cls.foreign = ChannelAccount.objects.create(organization=cls.other, channel=cls.channel)

    def inbound(self, **kwargs):
        args = dict(
            organization=self.org,
            account_id=self.account.pk,
            sender="identity",
            external_id="message",
            text="Hello",
        )
        args.update(kwargs)
        return services.persist_inbound_message(**args)

    def outbound(self):
        incoming = self.inbound()
        return services.create_outbound_message(
            organization=self.org,
            conversation_id=incoming.conversation_id,
            text="Reply",
            idempotency_key=uuid.uuid4(),
        )

    def test_inbound_retry_and_conflict(self):
        message = self.inbound()
        self.assertEqual(self.inbound().pk, message.pk)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Contact.objects.count(), 1)
        with self.assertRaises(services.CommunicationConflict):
            self.inbound(text="different")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Message.objects.create(
                organization=self.org,
                account=self.account,
                conversation=message.conversation,
                direction="INBOUND",
                status="RECEIVED",
                text="Duplicate",
                external_id="message",
            )

    def test_id_scope_and_identity_matching(self):
        first = self.inbound()
        second = self.inbound(external_id="two")
        self.assertEqual(first.conversation_id, second.conversation_id)
        foreign = self.inbound(organization=self.other, account_id=self.foreign.pk)
        self.assertNotEqual(first.conversation_id, foreign.conversation_id)
        another = ChannelAccount.objects.create(organization=self.org, channel=self.channel)
        distinct = self.inbound(account_id=another.pk)
        self.assertNotEqual(
            first.conversation.identity.contact_id, distinct.conversation.identity.contact_id
        )
        linked = services.find_or_create_contact(
            organization=self.org,
            account_id=another.pk,
            external_id="linked",
            contact_id=first.conversation.identity.contact_id,
        )
        self.assertEqual(linked.contact_id, first.conversation.identity.contact_id)
        with self.assertRaises(services.CommunicationConflict):
            services.find_or_create_contact(
                organization=self.org,
                account_id=another.pk,
                external_id="linked",
                contact_id=distinct.conversation.identity.contact_id,
            )

    def test_cross_tenant_references_rejected(self):
        foreign = self.inbound(organization=self.other, account_id=self.foreign.pk)
        with self.assertRaises(Http404):
            self.inbound(account_id=self.foreign.pk)
        with self.assertRaises(Http404):
            services.find_or_create_conversation(
                organization=self.org,
                identity_id=foreign.conversation.identity_id,
            )
        with self.assertRaises(Http404):
            services.create_outbound_message(
                organization=self.org,
                conversation_id=foreign.conversation_id,
                text="x",
                idempotency_key=uuid.uuid4(),
            )
        with self.assertRaises(Http404):
            services.update_delivery_status(
                organization=self.org, message_id=foreign.pk, status="SENT"
            )

    def test_outbound_idempotency(self):
        message = self.outbound()
        duplicate = services.create_outbound_message(
            organization=self.org,
            conversation_id=message.conversation_id,
            text=message.text,
            idempotency_key=message.idempotency_key,
        )
        self.assertEqual(message.pk, duplicate.pk)
        with self.assertRaises(services.CommunicationConflict):
            services.create_outbound_message(
                organization=self.org,
                conversation_id=message.conversation_id,
                text="changed",
                idempotency_key=message.idempotency_key,
            )

    def test_delivery_order_and_terminal_failures(self):
        message = self.outbound()

        def update(status, **kwargs):
            return services.update_delivery_status(
                organization=self.org,
                message_id=message.pk,
                status=status,
                **kwargs,
            )

        delivered = update("DELIVERED", external_id="out")
        self.assertEqual(update("SENT").status, "DELIVERED")
        self.assertEqual(update("DELIVERED").status_at, delivered.status_at)
        self.assertEqual(update("READ").status, "READ")
        with self.assertRaises(services.CommunicationConflict):
            update("FAILED")
        with self.assertRaises(services.CommunicationConflict):
            update("READ", external_id="changed")
        failed = self.outbound()
        services.update_delivery_status(
            organization=self.org, message_id=failed.pk, status="FAILED"
        )
        with self.assertRaises(services.CommunicationConflict):
            services.update_delivery_status(
                organization=self.org, message_id=failed.pk, status="SENT"
            )
        with self.assertRaises(services.CommunicationConflict):
            services.update_delivery_status(
                organization=self.org, message_id=self.inbound().pk, status="SENT"
            )

    def test_conversation_transition_graph(self):
        conversation = self.inbound().conversation
        for status in ["PENDING", "PENDING", "OPEN", "RESOLVED", "OPEN", "RESOLVED"]:
            result = services.change_conversation_status(
                organization=self.org,
                conversation_id=conversation.pk,
                status=status,
            )
            self.assertEqual(result.status, status)
        with self.assertRaises(services.CommunicationConflict):
            services.change_conversation_status(
                organization=self.org,
                conversation_id=conversation.pk,
                status="PENDING",
            )

    def test_api_authorization_ownership_and_ordering(self):
        now = timezone.now()
        latest = self.inbound(occurred_at=now)
        earliest = self.inbound(external_id="early", occurred_at=now - timedelta(days=1))
        foreign = self.inbound(organization=self.other, account_id=self.foreign.pk)
        base = f"/api/v1/organizations/{self.org.pk}/conversations/"
        client = APIClient()
        self.assertEqual(client.get(base).status_code, 401)
        client.force_authenticate(self.user)
        self.assertEqual(client.get(base).data["count"], 1)
        self.assertEqual(client.get(base + f"{foreign.conversation_id}/").status_code, 404)
        self.assertEqual(client.get(base + f"{foreign.conversation_id}/messages/").status_code, 404)
        self.assertEqual(
            client.patch(base + f"{foreign.conversation_id}/", {"status": "RESOLVED"}).status_code,
            404,
        )
        detail = base + f"{latest.conversation_id}/"
        self.assertEqual(client.get(detail).status_code, 200)
        result = client.get(detail + "messages/")
        self.assertEqual(
            [item["id"] for item in result.data["results"]], [str(earliest.pk), str(latest.pk)]
        )
        self.assertEqual(client.patch(detail, {"status": "RESOLVED"}).status_code, 200)
        self.assertEqual(client.patch(detail, {"status": "PENDING"}).status_code, 400)
        self.assertEqual(client.patch(detail, {"status": "INVALID"}).status_code, 400)
        self.assertEqual(
            client.get(f"/api/v1/organizations/{self.other.pk}/conversations/").status_code, 404
        )
        set_capability(self.org, Capability.SHARED_INBOX, enabled=False)
        self.assertEqual(client.get(base).status_code, 403)

    def test_delivery_id_collision_and_metadata_validation(self):
        message = self.outbound()
        with self.assertRaises(services.CommunicationConflict):
            services.update_delivery_status(
                organization=self.org,
                message_id=message.pk,
                status="SENT",
                external_id="message",
            )
        message.refresh_from_db()
        self.assertEqual(message.status, "QUEUED")
        self.assertIsNone(message.external_id)
        with self.assertRaises(services.ValidationError):
            self.inbound(external_id="bad-metadata", metadata=[])
        self.assertEqual(Message.objects.count(), 2)

    def test_required_tenant_and_state_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contact.objects.create()
        message = self.inbound()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Message.objects.filter(pk=message.pk).update(status="SENT")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.filter(pk=message.conversation_id).update(status="INVALID")
        self.assertEqual(ContactIdentity.objects.count(), 1)


class ConcurrentInboundTests(TransactionTestCase):
    def test_simultaneous_webhook_retries_create_one_message(self):
        organization = Organization.objects.create(name="Concurrent")
        channel, _ = Channel.objects.get_or_create(code="WHATSAPP")
        account = ChannelAccount.objects.create(organization=organization, channel=channel)

        def persist(_):
            close_old_connections()
            try:
                return services.persist_inbound_message(
                    organization=organization,
                    account_id=account.pk,
                    sender="same-sender",
                    external_id="same-event",
                    text="same-text",
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(persist, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Contact.objects.count(), 1)
