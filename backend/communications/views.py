from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response

from billing.definitions import Capability
from billing.services import require_capability
from communications.models import Conversation, Message
from communications.serializers import (
    ConversationSerializer,
    ConversationStatusSerializer,
    MessageSerializer,
)
from communications.services import change_conversation_status
from core.services import locked_actor
from core.tenancy import resolve_membership


def authorized_organization(request, organization_id):
    membership = resolve_membership(request.user, organization_id)
    require_capability(membership.organization, Capability.SHARED_INBOX)
    return membership.organization


class ConversationList(generics.ListAPIView):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        organization = authorized_organization(self.request, self.kwargs["organization_id"])
        return Conversation.objects.filter(organization=organization).order_by("-created_at", "id")


class ConversationDetail(generics.RetrieveAPIView):
    serializer_class = ConversationSerializer
    lookup_url_kwarg = "conversation_id"

    def get_queryset(self):
        organization = authorized_organization(self.request, self.kwargs["organization_id"])
        return Conversation.objects.filter(organization=organization)

    @transaction.atomic
    def patch(self, request, organization_id, conversation_id):
        membership = locked_actor(request.user, organization_id)
        require_capability(membership.organization, Capability.SHARED_INBOX)
        serializer = ConversationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = change_conversation_status(
            organization=membership.organization,
            conversation_id=conversation_id,
            **serializer.validated_data,
        )
        return Response(ConversationSerializer(conversation).data)


class MessageList(generics.ListAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        organization = authorized_organization(self.request, self.kwargs["organization_id"])
        conversation = get_object_or_404(
            Conversation.objects.filter(organization=organization),
            pk=self.kwargs["conversation_id"],
        )
        return Message.objects.filter(organization=organization, conversation=conversation)
