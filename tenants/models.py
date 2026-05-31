"""ORM models for multi-tenant workspaces, memberships and invites."""
import uuid

from django.conf import settings
from django.db import models


class WorkspaceRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    EDITOR = "editor", "Editor"
    VIEWER = "viewer", "Viewer"


ADMIN_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}
INVITE_ROLES = {WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER}


class Workspace(models.Model):
    """Tenant container; owner is denormalized from owner membership."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(models.Model):
    """User membership in a workspace with a role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    role = models.CharField(max_length=16, choices=WorkspaceRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                name="unique_workspace_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.workspace_id} ({self.role})"


class WorkspaceInvite(models.Model):
    """Email invite to join a workspace; token stored as hash only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=16, choices=WorkspaceRole.choices)
    token_hash = models.CharField(max_length=64, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_workspace_invites",
    )
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "email"]),
        ]

    def __str__(self) -> str:
        return f"Invite {self.email} → {self.workspace_id}"
