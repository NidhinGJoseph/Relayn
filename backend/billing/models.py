import uuid

from django.db import models

from billing.definitions import Capability, Limit


class OrganizationEntitlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="entitlements"
    )
    key = models.CharField(max_length=32, choices=Capability.choices + Limit.choices)
    enabled = models.BooleanField(null=True)
    limit = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key"], name="unique_organization_entitlement"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(key__in=Capability.values, enabled__isnull=False, limit__isnull=True)
                    | models.Q(
                        key__in=Limit.values,
                        enabled__isnull=True,
                        limit__isnull=False,
                        limit__gte=0,
                    )
                ),
                name="valid_entitlement_value",
            ),
        ]
