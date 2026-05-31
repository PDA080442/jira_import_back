"""Membership lookup and role checks."""
from accounts.models import User
from tenants.models import ADMIN_ROLES, Workspace, WorkspaceMembership, WorkspaceRole
from core.exceptions import ApiError
from rest_framework import status


def get_membership(*, user: User, workspace: Workspace) -> WorkspaceMembership | None:
    return WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()


def require_membership(*, user: User, workspace: Workspace) -> WorkspaceMembership:
    membership = get_membership(user=user, workspace=workspace)
    if membership is None:
        raise ApiError(
            detail="Workspace not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return membership


def user_has_admin_role(*, user: User, workspace: Workspace) -> bool:
    membership = get_membership(user=user, workspace=workspace)
    return membership is not None and membership.role in ADMIN_ROLES


def user_is_owner(*, user: User, workspace: Workspace) -> bool:
    if workspace.owner_id == user.id:
        return True
    membership = get_membership(user=user, workspace=workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def list_members(*, workspace: Workspace) -> list[WorkspaceMembership]:
    return list(
        WorkspaceMembership.objects.filter(workspace=workspace)
        .select_related("user")
        .order_by("created_at"),
    )
