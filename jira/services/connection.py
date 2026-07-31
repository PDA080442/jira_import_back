"""Jira connection CRUD and access control."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from jira.models import JiraConnection, JiraTestStatus
from jira.services.crypto import encrypt_secret
from rest_framework import status
from tenants.models import Workspace
from tenants.services.membership import require_membership, user_has_admin_role
from tenants.services.workspace import get_workspace

logger = get_logger("jira.connection")


def _require_admin(*, user: User, workspace: Workspace, action: str) -> None:
    if not user_has_admin_role(user=user, workspace=workspace):
        logger.warning(
            "jira_connection_access_forbidden",
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            action=action,
        )
        raise ApiError(
            detail="You do not have permission to manage Jira connections.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _connection_audit_payload(connection: JiraConnection) -> dict:
    return {
        "connection_id": str(connection.id),
        "name": connection.name,
        "base_url": connection.base_url,
        "email": connection.email,
        "project_key": connection.project_key,
        "board_id": connection.board_id,
        "is_active": connection.is_active,
    }


def get_connection(*, workspace_id, connection_id, user: User) -> JiraConnection:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    try:
        connection = JiraConnection.objects.get(pk=connection_id, workspace=workspace)
    except JiraConnection.DoesNotExist as exc:
        raise ApiError(
            detail="Jira connection not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    return connection


def list_connections(*, workspace_id, user: User):
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    require_membership(user=user, workspace=workspace)
    return JiraConnection.objects.filter(workspace=workspace).order_by("-created_at")


@transaction.atomic
def create_connection(
    *,
    workspace_id,
    user: User,
    name: str,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    board_id: str = "",
    extra: dict | None = None,
    is_active: bool = True,
) -> JiraConnection:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    _require_admin(user=user, workspace=workspace, action="create")

    try:
        connection = JiraConnection.objects.create(
            workspace=workspace,
            name=name,
            base_url=base_url,
            email=email,
            api_token_encrypted=encrypt_secret(api_token),
            project_key=project_key,
            board_id=board_id or "",
            extra=extra or {},
            is_active=is_active,
            created_by=user,
        )
    except IntegrityError as exc:
        raise ApiError(
            detail="A connection with this name already exists in the workspace.",
            code="VALIDATION_ERROR",
            field_errors={"name": ["Connection name must be unique within workspace."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    log_action(
        action="jira_connection.create",
        entity_type="jira_connection",
        entity_id=str(connection.id),
        actor=user,
        payload=_connection_audit_payload(connection),
    )
    logger.info(
        "jira_connection_created",
        connection_id=str(connection.id),
        workspace_id=str(workspace.id),
    )
    return connection


@transaction.atomic
def update_connection(
    *,
    connection: JiraConnection,
    user: User,
    name: str | None = None,
    base_url: str | None = None,
    email: str | None = None,
    api_token: str | None = None,
    project_key: str | None = None,
    board_id: str | None = None,
    extra: dict | None = None,
    is_active: bool | None = None,
) -> JiraConnection:
    _require_admin(user=user, workspace=connection.workspace, action="update")

    update_fields = ["updated_at"]
    if name is not None:
        connection.name = name
        update_fields.append("name")
    if base_url is not None:
        connection.base_url = base_url
        update_fields.append("base_url")
    if email is not None:
        connection.email = email
        update_fields.append("email")
    if api_token is not None:
        connection.api_token_encrypted = encrypt_secret(api_token)
        update_fields.append("api_token_encrypted")
    if project_key is not None:
        connection.project_key = project_key
        update_fields.append("project_key")
    if board_id is not None:
        connection.board_id = board_id
        update_fields.append("board_id")
    if extra is not None:
        connection.extra = extra
        update_fields.append("extra")
    if is_active is not None:
        connection.is_active = is_active
        update_fields.append("is_active")

    try:
        connection.save(update_fields=update_fields)
    except IntegrityError as exc:
        raise ApiError(
            detail="A connection with this name already exists in the workspace.",
            code="VALIDATION_ERROR",
            field_errors={"name": ["Connection name must be unique within workspace."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    log_action(
        action="jira_connection.update",
        entity_type="jira_connection",
        entity_id=str(connection.id),
        actor=user,
        payload=_connection_audit_payload(connection),
    )
    logger.info("jira_connection_updated", connection_id=str(connection.id))
    return connection


@transaction.atomic
def deactivate_connection(*, connection: JiraConnection, user: User) -> JiraConnection:
    _require_admin(user=user, workspace=connection.workspace, action="deactivate")
    connection.is_active = False
    connection.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="jira_connection.deactivate",
        entity_type="jira_connection",
        entity_id=str(connection.id),
        actor=user,
        payload=_connection_audit_payload(connection),
    )
    logger.info("jira_connection_deactivated", connection_id=str(connection.id))
    return connection
