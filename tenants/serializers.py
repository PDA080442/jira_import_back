"""DRF serializers for workspace API input/output."""
from rest_framework import serializers

from accounts.models import User
from tenants.constants import MAX_WORKSPACE_NAME_LENGTH, MIN_WORKSPACE_NAME_LENGTH
from tenants.models import INVITE_ROLES, Workspace, WorkspaceMembership, WorkspaceRole


class WorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=MAX_WORKSPACE_NAME_LENGTH,
        min_length=MIN_WORKSPACE_NAME_LENGTH,
        help_text="Display name; slug is derived automatically and cannot be set here.",
    )


class WorkspaceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=MAX_WORKSPACE_NAME_LENGTH,
        min_length=MIN_WORKSPACE_NAME_LENGTH,
        help_text="New workspace display name (admin or owner only).",
    )


class WorkspaceSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True, help_text="Workspace primary key.")
    name = serializers.CharField(read_only=True, help_text="Display name.")
    slug = serializers.CharField(read_only=True, help_text="URL-safe unique slug (auto-generated, immutable).")
    owner_id = serializers.UUIDField(read_only=True, help_text="UUID of the workspace owner user.")
    created_at = serializers.DateTimeField(read_only=True, help_text="Creation timestamp (UTC).")
    updated_at = serializers.DateTimeField(read_only=True, help_text="Last update timestamp (UTC).")

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
    id = serializers.UUIDField(read_only=True, help_text="Membership record id.")
    user_id = serializers.UUIDField(read_only=True, help_text="User UUID.")
    email = serializers.EmailField(read_only=True, help_text="Member email.")
    role = serializers.CharField(read_only=True, help_text="Role: owner, admin, editor, or viewer.")
    joined_at = serializers.DateTimeField(read_only=True, help_text="When the user joined the workspace (UTC).")

    def to_representation(self, membership: WorkspaceMembership):
        return {
            "id": membership.id,
            "user_id": membership.user_id,
            "email": membership.user.email,
            "role": membership.role,
            "joined_at": membership.created_at,
        }


class WorkspaceInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Invitee email; must match on accept.")
    role = serializers.ChoiceField(
        choices=[(role.value, role.label) for role in sorted(INVITE_ROLES, key=lambda r: r.value)],
        help_text="Membership role: admin, editor, or viewer (owner is not allowed).",
    )

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class WorkspaceInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Raw invite token from the invitation email link.")


class WorkspaceInviteResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True, help_text="Invite record id.")
    email = serializers.EmailField(read_only=True, help_text="Invited email address.")
    role = serializers.CharField(read_only=True, help_text="Role assigned on accept.")
    expires_at = serializers.DateTimeField(read_only=True, help_text="Invite expiry (UTC). Token is not returned in API.")

    def to_representation(self, invite):
        return {
            "id": invite.id,
            "email": invite.email,
            "role": invite.role,
            "expires_at": invite.expires_at,
        }
