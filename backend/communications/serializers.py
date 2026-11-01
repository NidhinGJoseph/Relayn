from rest_framework import serializers

from communications.models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "identity", "status", "created_at", "updated_at"]
        read_only_fields = fields


class ConversationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Conversation.Status.choices)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "direction",
            "kind",
            "text",
            "external_id",
            "status",
            "occurred_at",
            "status_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
