"""Access control for source files."""
from accounts.models import User
from core.exceptions import ApiError
from rest_framework import status
from sources.models import GoogleSheetSource, SourceFile
from tenants.models import Workspace, WorkspaceRole
from tenants.services.membership import get_membership, require_membership
from tenants.services.workspace import get_workspace

EDITOR_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR}


def _require_editor(*, user: User, workspace: Workspace, action: str) -> None:
    from core.logging import get_logger

    membership = get_membership(user=user, workspace=workspace)
    if membership is None or membership.role not in EDITOR_ROLES:
        get_logger("sources.access").warning(
            "source_file_access_forbidden",
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            action=action,
        )
        raise ApiError(
            detail="You do not have permission to manage source files.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def get_source_file(*, workspace_id, source_id, user: User) -> SourceFile:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    try:
        return SourceFile.objects.select_related("active_snapshot", "applied_preset").prefetch_related(
            "sheets",
        ).get(
            pk=source_id,
            workspace=workspace,
        )
    except SourceFile.DoesNotExist as exc:
        raise ApiError(
            detail="Source file not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc


def require_member(*, workspace_id, user: User):
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    require_membership(user=user, workspace=workspace)
    return workspace


def get_google_source(*, workspace_id, source_id, user: User) -> GoogleSheetSource:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    try:
        return GoogleSheetSource.objects.select_related(
            "active_snapshot",
            "applied_preset",
        ).prefetch_related("tabs").get(
            pk=source_id,
            workspace=workspace,
        )
    except GoogleSheetSource.DoesNotExist as exc:
        raise ApiError(
            detail="Google Sheet source not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
