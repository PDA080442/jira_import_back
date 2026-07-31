"""DRF permission classes for workspace tenant access."""
from rest_framework.permissions import BasePermission

from tenants.models import ADMIN_ROLES, Workspace, WorkspaceMembership


class IsWorkspaceMember(BasePermission):
    """User has any membership in workspace from URL pk."""

    message = "You are not a member of this workspace."

    def has_permission(self, request, view):
        workspace_id = view.kwargs.get("pk")
        if not workspace_id or not request.user.is_authenticated:
            return False
        return WorkspaceMembership.objects.filter(
            workspace_id=workspace_id,
            user=request.user,
        ).exists()


class IsWorkspaceAdmin(BasePermission):
    """User has owner or admin role in workspace from URL pk."""

    message = "Admin access required."

    def has_permission(self, request, view):
        workspace_id = view.kwargs.get("pk")
        if not workspace_id or not request.user.is_authenticated:
            return False
        return WorkspaceMembership.objects.filter(
            workspace_id=workspace_id,
            user=request.user,
            role__in=ADMIN_ROLES,
        ).exists()


class IsWorkspaceOwner(BasePermission):
    """User is workspace owner (FK or owner role)."""

    message = "Owner access required."

    def has_permission(self, request, view):
        workspace_id = view.kwargs.get("pk")
        if not workspace_id or not request.user.is_authenticated:
            return False
        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            return False
        if workspace.owner_id == request.user.id:
            return True
        return WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=request.user,
            role="owner",
        ).exists()
