"""DRF serializers for workspace API input/output."""
from rest_framework import serializers

from accounts.models import User
from tenants.models import INVITE_ROLES, Workspace, WorkspaceMembership, WorkspaceRole


class WorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, min_length=1)


class WorkspaceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, min_length=1)


class WorkspaceSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    owner_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, workspace: Workspace):
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "owner_id": str(workspace.owner_id),
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }


class WorkspaceMemberSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.CharField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, membership: WorkspaceMembership):
        return {
            "id": membership.id,
            "user_id": membership.user_id,
            "email": membership.user.email,
            "role": membership.role,
            "joined_at": membership.created_at,
        }


class WorkspaceInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[(role.value, role.label) for role in sorted(INVITE_ROLES, key=lambda r: r.value)],
    )

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class WorkspaceInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()


class WorkspaceInviteResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, invite):
        return {
            "id": invite.id,
            "email": invite.email,
            "role": invite.role,
            "expires_at": invite.expires_at,
        }
