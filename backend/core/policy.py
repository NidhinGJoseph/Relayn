from enum import StrEnum

from rest_framework.exceptions import PermissionDenied

from core.models import OrganizationMembership


class Capability(StrEnum):
    ORGANIZATION_VIEW = "organization.view"
    MEMBERS_VIEW = "members.view"
    MEMBERS_CREATE = "members.create"
    MEMBERS_CHANGE_ROLE = "members.change_role"
    MEMBERS_REMOVE = "members.remove"


Role = OrganizationMembership.Role
READ = frozenset({Capability.ORGANIZATION_VIEW, Capability.MEMBERS_VIEW})
ROLE_CAPABILITIES = {
    Role.OWNER: frozenset(Capability),
    Role.ADMIN: frozenset(Capability),
    Role.MANAGER: READ,
    Role.AGENT: READ,
}
MANAGEABLE_ROLES = {
    Role.OWNER: frozenset(Role),
    Role.ADMIN: frozenset({Role.MANAGER, Role.AGENT}),
    Role.MANAGER: frozenset(),
    Role.AGENT: frozenset(),
}


def require_capability(membership, capability):
    if capability not in ROLE_CAPABILITIES.get(membership.role, frozenset()):
        raise PermissionDenied()


def require_role_authority(membership, *roles):
    if not set(roles).issubset(MANAGEABLE_ROLES.get(membership.role, frozenset())):
        raise PermissionDenied()
