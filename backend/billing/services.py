"""Organization entitlements, independent of pricing and member role permissions.

Read callers must first authorize organization context (core.tenancy for requests).
Assignment functions are trusted operator-only interfaces, never tenant APIs.
"""

from rest_framework.exceptions import PermissionDenied

from billing.definitions import Capability, Limit
from billing.models import OrganizationEntitlement
from core.models import Organization


class CapabilityUnavailable(PermissionDenied):
    default_detail = "The organization does not have the required capability."
    default_code = "capability_unavailable"


def _organization_id(organization):
    if not isinstance(organization, Organization) or organization._state.adding:
        raise ValueError("A persisted, authorized organization is required.")
    return organization.pk


def has_capability(organization, key):
    key = Capability(key)
    return OrganizationEntitlement.objects.filter(
        organization_id=_organization_id(organization), key=key, enabled=True
    ).exists()


def get_limit(organization, key):
    key = Limit(key)
    return (
        OrganizationEntitlement.objects.filter(
            organization_id=_organization_id(organization), key=key
        )
        .values_list("limit", flat=True)
        .first()
    )


def require_capability(organization, key):
    if not has_capability(organization, key):
        raise CapabilityUnavailable()


def set_capability(organization, key, *, enabled):
    """Assign explicitly from trusted internal/operator code only."""
    key = Capability(key)
    if type(enabled) is not bool:
        raise ValueError("enabled must be a boolean.")
    entitlement, _ = OrganizationEntitlement.objects.update_or_create(
        organization_id=_organization_id(organization),
        key=key,
        defaults={"enabled": enabled, "limit": None},
    )
    return entitlement


def set_limit(organization, key, *, value):
    """Assign an explicit nonnegative integer; no unlimited sentinel exists."""
    key = Limit(key)
    if type(value) is not int or not 0 <= value <= 9223372036854775807:
        raise ValueError("value must be a nonnegative signed 64-bit integer.")
    entitlement, _ = OrganizationEntitlement.objects.update_or_create(
        organization_id=_organization_id(organization),
        key=key,
        defaults={"enabled": None, "limit": value},
    )
    return entitlement
