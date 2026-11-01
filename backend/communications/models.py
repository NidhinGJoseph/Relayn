import uuid

from django.db import models
from django.utils import timezone


class TenantRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("core.Organization", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Contact(TenantRecord):
    display_name = models.CharField(max_length=200, blank=True)


class ContactIdentity(TenantRecord):
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="identities")
    account = models.ForeignKey("channels.ChannelAccount", on_delete=models.PROTECT)
    external_id = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "account", "external_id"], name="unique_contact_identity"
            ),
            models.CheckConstraint(condition=~models.Q(external_id=""), name="nonempty_identity"),
        ]


class Conversation(TenantRecord):
    class Status(models.TextChoices):
        OPEN = "OPEN"
        PENDING = "PENDING"
        RESOLVED = "RESOLVED"

    identity = models.ForeignKey(ContactIdentity, on_delete=models.PROTECT)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "identity"], name="unique_identity_conversation"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["OPEN", "PENDING", "RESOLVED"]),
                name="valid_conversation_status",
            ),
        ]


class MessageStatus(models.TextChoices):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class Message(TenantRecord):
    class Direction(models.TextChoices):
        INBOUND = "INBOUND"
        OUTBOUND = "OUTBOUND"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="messages"
    )
    account = models.ForeignKey("channels.ChannelAccount", on_delete=models.PROTECT)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    kind = models.CharField(max_length=4, default="TEXT", choices=[("TEXT", "Text")])
    text = models.TextField()
    external_id = models.CharField(max_length=255, null=True, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=MessageStatus.choices)
    occurred_at = models.DateTimeField(default=timezone.now)
    status_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["occurred_at", "created_at", "id"]
        indexes = [models.Index(fields=["organization", "conversation", "occurred_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "account", "external_id"], name="unique_account_message"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"], name="unique_outbound_request"
            ),
            models.CheckConstraint(condition=models.Q(kind="TEXT"), name="message_text_only"),
            models.CheckConstraint(condition=~models.Q(external_id=""), name="nonempty_message_id"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        direction="INBOUND",
                        status="RECEIVED",
                        external_id__isnull=False,
                        idempotency_key__isnull=True,
                    )
                    | models.Q(
                        direction="OUTBOUND",
                        idempotency_key__isnull=False,
                        status__in=["QUEUED", "SENT", "DELIVERED", "READ", "FAILED"],
                    )
                ),
                name="valid_message_state",
            ),
        ]
