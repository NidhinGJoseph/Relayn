from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.models import Organization, OrganizationMembership
from core.policy import Capability, require_capability
from core.serializers import (
    AddMemberSerializer,
    ChangeRoleSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    UserSerializer,
)
from core.tenancy import resolve_membership


class CurrentUser(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class OrganizationList(generics.ListAPIView):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user).order_by(
            "created_at", "id"
        )


class OrganizationDetail(APIView):
    def get(self, request, organization_id):
        membership = resolve_membership(request.user, organization_id)
        require_capability(membership, Capability.ORGANIZATION_VIEW)
        return Response(OrganizationSerializer(membership.organization).data)


class MemberList(generics.ListAPIView):
    serializer_class = MembershipSerializer

    def get_queryset(self):
        membership = resolve_membership(self.request.user, self.kwargs["organization_id"])
        require_capability(membership, Capability.MEMBERS_VIEW)
        return (
            OrganizationMembership.objects.filter(organization=membership.organization)
            .select_related("user")
            .order_by("created_at", "id")
        )

    def post(self, request, organization_id):
        membership = resolve_membership(request.user, organization_id)
        require_capability(membership, Capability.MEMBERS_CREATE)
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.add_member(
            actor=request.user, organization_id=organization_id, **serializer.validated_data
        )
        return Response(MembershipSerializer(member).data, status=status.HTTP_201_CREATED)


class MemberDetail(APIView):
    def patch(self, request, organization_id, membership_id):
        membership = resolve_membership(request.user, organization_id)
        require_capability(membership, Capability.MEMBERS_CHANGE_ROLE)
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.change_member_role(
            actor=request.user,
            organization_id=organization_id,
            membership_id=membership_id,
            **serializer.validated_data,
        )
        return Response(MembershipSerializer(member).data)

    def delete(self, request, organization_id, membership_id):
        services.remove_member(
            actor=request.user, organization_id=organization_id, membership_id=membership_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
