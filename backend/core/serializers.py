from rest_framework import serializers

from core.models import Organization, OrganizationMembership, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ["id", "user", "role", "created_at", "updated_at"]
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=OrganizationMembership.Role.choices)


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=OrganizationMembership.Role.choices)
