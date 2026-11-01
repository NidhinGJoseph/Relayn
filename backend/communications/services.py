"""Trusted persistence boundary; callers authorize organization before use.

All writes lock the tenant row, protecting creation and cross-object checks.
Direct ORM writes are unsupported. No provider dispatch occurs here.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from channels.models import ChannelAccount
from communications.models import Contact, ContactIdentity, Conversation, Message, MessageStatus
from core.models import Organization


class CommunicationConflict(ValidationError):
    default_detail = "Conflicting communication operation."
    default_code = "communication_conflict"


def lock_organization(organization):
    if not isinstance(organization, Organization) or organization._state.adding:
        raise ValueError("A persisted, authorized organization is required.")
    return get_object_or_404(Organization.objects.select_for_update(), pk=organization.pk)


def scoped(model, organization, pk):
    return get_object_or_404(model.objects.filter(organization=organization), pk=pk)


def save_record(record):
    if isinstance(record, Message) and not isinstance(record.metadata, dict):
        raise ValidationError("Message metadata must be an object.")
    record.full_clean()
    record.save()
    return record


@transaction.atomic
def find_or_create_contact(*, organization, account_id, external_id, contact_id=None):
    lock_organization(organization)
    account = scoped(ChannelAccount, organization, account_id)
    contact = scoped(Contact, organization, contact_id) if contact_id else None
    identity = ContactIdentity.objects.filter(
        organization=organization, account=account, external_id=external_id
    ).first()
    if identity:
        if contact and identity.contact_id != contact.pk:
            raise CommunicationConflict("Identity already belongs to another contact.")
        return identity
    if not isinstance(external_id, str) or not external_id or len(external_id) > 255:
        raise ValidationError("A nonempty channel-normalized identity (max 255) is required.")
    contact = contact or Contact.objects.create(organization=organization)
    return save_record(
        ContactIdentity(
            organization=organization, account=account, contact=contact, external_id=external_id
        )
    )


@transaction.atomic
def find_or_create_conversation(*, organization, identity_id):
    lock_organization(organization)
    identity = scoped(ContactIdentity, organization, identity_id)
    scoped(Contact, organization, identity.contact_id)
    scoped(ChannelAccount, organization, identity.account_id)
    return Conversation.objects.get_or_create(organization=organization, identity=identity)[0]


CONVERSATION_TRANSITIONS = {
    "OPEN": {"PENDING", "RESOLVED"},
    "PENDING": {"OPEN", "RESOLVED"},
    "RESOLVED": {"OPEN"},
}


@transaction.atomic
def change_conversation_status(*, organization, conversation_id, status):
    lock_organization(organization)
    conversation = scoped(Conversation, organization, conversation_id)
    if status == conversation.status:
        return conversation
    if status not in CONVERSATION_TRANSITIONS[conversation.status]:
        raise CommunicationConflict("Invalid conversation status transition.")
    conversation.status = status
    conversation.save(update_fields=["status", "updated_at"])
    return conversation


@transaction.atomic
def persist_inbound_message(
    *, organization, account_id, sender, external_id, text, occurred_at=None, metadata=None
):
    lock_organization(organization)
    account = scoped(ChannelAccount, organization, account_id)
    if not isinstance(external_id, str) or not external_id or len(external_id) > 255:
        raise ValidationError("A nonempty external message ID (max 255) is required.")
    existing = (
        Message.objects.filter(organization=organization, account=account, external_id=external_id)
        .select_related("conversation__identity")
        .first()
    )
    if existing:
        if (
            existing.direction != "INBOUND"
            or existing.text != text
            or existing.conversation.identity.external_id != sender
        ):
            raise CommunicationConflict("External message ID was already used.")
        return existing
    identity = find_or_create_contact(
        organization=organization, account_id=account.pk, external_id=sender
    )
    conversation = find_or_create_conversation(organization=organization, identity_id=identity.pk)
    timestamp = occurred_at or timezone.now()
    return save_record(
        Message(
            organization=organization,
            conversation=conversation,
            account=account,
            direction="INBOUND",
            external_id=external_id,
            text=text,
            status=MessageStatus.RECEIVED,
            occurred_at=timestamp,
            status_at=timestamp,
            metadata=metadata if metadata is not None else {},
        )
    )


@transaction.atomic
def create_outbound_message(*, organization, conversation_id, text, idempotency_key, metadata=None):
    lock_organization(organization)
    conversation = scoped(Conversation, organization, conversation_id)
    identity = scoped(ContactIdentity, organization, conversation.identity_id)
    scoped(Contact, organization, identity.contact_id)
    account = scoped(ChannelAccount, organization, identity.account_id)
    if idempotency_key is None:
        raise ValidationError("An outbound idempotency key is required.")
    existing = Message.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.conversation_id != conversation.pk or existing.text != text:
            raise CommunicationConflict("Outbound idempotency key was already used.")
        return existing
    return save_record(
        Message(
            organization=organization,
            conversation=conversation,
            account=account,
            direction="OUTBOUND",
            text=text,
            status=MessageStatus.QUEUED,
            idempotency_key=idempotency_key,
            metadata=metadata if metadata is not None else {},
        )
    )


# Forward skips allow missing provider events; late lower-rank events are no-ops.
DELIVERY_RANK = {"QUEUED": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}


@transaction.atomic
def update_delivery_status(*, organization, message_id, status, external_id=None, occurred_at=None):
    lock_organization(organization)
    message = scoped(Message, organization, message_id)
    original = (message.status, message.external_id)
    if message.direction != "OUTBOUND" or status not in {*DELIVERY_RANK, "FAILED"}:
        raise CommunicationConflict("Invalid delivery status.")
    if external_id is not None:
        if not isinstance(external_id, str) or not external_id or len(external_id) > 255:
            raise ValidationError("Invalid external message ID.")
        if message.external_id and message.external_id != external_id:
            raise CommunicationConflict("External message ID cannot change.")
        if (
            Message.objects.filter(
                organization=organization, account_id=message.account_id, external_id=external_id
            )
            .exclude(pk=message.pk)
            .exists()
        ):
            raise CommunicationConflict("External message ID was already used.")
        message.external_id = external_id
    if status != message.status:
        if message.status == "FAILED":
            raise CommunicationConflict("Failed messages are terminal; create a new attempt.")
        if status == "FAILED":
            if message.status in {"DELIVERED", "READ"}:
                raise CommunicationConflict("Delivered messages cannot fail.")
        elif DELIVERY_RANK[status] < DELIVERY_RANK[message.status]:
            status = message.status
        if status != message.status:
            message.status = status
            message.status_at = max(message.status_at, occurred_at or timezone.now())
    if (message.status, message.external_id) == original:
        return message
    return save_record(message)
