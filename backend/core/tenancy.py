from django.shortcuts import get_object_or_404

from core.models import OrganizationMembership


def resolve_membership(user, organization_id):
    return get_object_or_404(
        OrganizationMembership.objects.select_related("organization").filter(
            user=user, user__is_active=True
        ),
        organization_id=organization_id,
    )
