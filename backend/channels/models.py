import uuid

from django.db import models


class Channel(models.Model):
    class Type(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"

    code = models.CharField(primary_key=True, max_length=32, choices=Type.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__in=["WHATSAPP"]), name="valid_channel_code"
            )
        ]


class ChannelAccount(models.Model):
    class Status(models.TextChoices):
        INACTIVE = "INACTIVE"
        ACTIVE = "ACTIVE"
        DISABLED = "DISABLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="channel_accounts"
    )
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="accounts")
    name = models.CharField(max_length=200)
    provider = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.INACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["INACTIVE", "ACTIVE", "DISABLED"]),
                name="valid_channel_account_status",
            )
        ]
