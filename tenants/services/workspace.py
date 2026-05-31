"""Workspace CRUD business logic."""
from django.db import transaction

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from rest_framework import status
from tenants.models import Workspace, WorkspaceMembership, WorkspaceRole
from tenants.services.membership import user_has_admin_role, user_is_owner
from tenants.services.slug import build_unique_slug

logger = get_logger("tenants.workspace")


def list_workspaces(*, user: User):
    return (
        Workspace.objects.filter(memberships__user=user)
        .select_related("owner")
        .distinct()
        .order_by("-created_at")
    )


def get_workspace(*, workspace_id, user: User) -> Workspace:
    try:
        workspace = Workspace.objects.select_related("owner").get(pk=workspace_id)
    except Workspace.DoesNotExist as exc:
        logger.warning("workspace_access_not_found", user_id=str(user.id))
        raise ApiError(
            detail="Workspace not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc

    if not WorkspaceMembership.objects.filter(workspace=workspace, user=user).exists():
        logger.warning("workspace_access_not_found", user_id=str(user.id))
        raise ApiError(
            detail="Workspace not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return workspace


@transaction.atomic
def create_workspace(*, user: User, name: str) -> Workspace:
    slug = build_unique_slug(name)
    workspace = Workspace.objects.create(name=name, slug=slug, owner=user)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceRole.OWNER,
    )
    log_action(
        action="workspace.create",
        entity_type="workspace",
        entity_id=str(workspace.id),
        actor=user,
        payload={"name": name, "slug": slug},
    )
    logger.info("workspace_created", workspace_id=str(workspace.id), user_id=str(user.id))
    return workspace


def update_workspace(*, workspace: Workspace, user: User, name: str) -> Workspace:
    if not user_has_admin_role(user=user, workspace=workspace):
        logger.warning(
            "workspace_access_forbidden",
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            action="update",
        )
        raise ApiError(
            detail="You do not have permission to update this workspace.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    workspace.name = name
    workspace.save(update_fields=["name", "updated_at"])
    log_action(
        action="workspace.update",
        entity_type="workspace",
        entity_id=str(workspace.id),
        actor=user,
        payload={"name": name},
    )
    logger.info("workspace_updated", workspace_id=str(workspace.id))
    return workspace


def delete_workspace(*, workspace: Workspace, user: User) -> None:
    if not user_is_owner(user=user, workspace=workspace):
        logger.warning(
            "workspace_access_forbidden",
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            action="delete",
        )
        raise ApiError(
            detail="Only the workspace owner can delete it.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    workspace_id = str(workspace.id)
    workspace.delete()
    log_action(
        action="workspace.delete",
        entity_type="workspace",
        entity_id=workspace_id,
        actor=user,
        payload={"workspace_id": workspace_id},
    )
    logger.info("workspace_deleted", workspace_id=workspace_id)
