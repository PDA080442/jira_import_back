"""Jira project metadata cache and sync pipeline."""
import time
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from jira.constants import JIRA_METADATA_DEFAULT_TTL_SECONDS
from jira.models import (
    JiraBoard,
    JiraField,
    JiraIssueType,
    JiraMetadataItem,
    JiraMetadataItemKind,
    JiraProjectMetadata,
    JiraSprint,
    JiraSyncStatus,
)
from jira.services.connection import _require_admin, get_connection
from jira.services.crypto import decrypt_secret
from jira.services.jira_client import (
    JiraAuthError,
    JiraClientError,
    JiraMetadataFetchResult,
    fetch_project_metadata,
)
from rest_framework import status
from tenants.services.membership import require_membership

logger = get_logger("jira.metadata")


def normalize_field_type(field_data: dict[str, Any]) -> str:
    """Map Jira field schema to template-friendly type."""
    from jira.constants import JIRA_CUSTOM_TYPE_TO_TEMPLATE, JIRA_SCHEMA_TYPE_TO_TEMPLATE

    schema = field_data.get("schema") or {}
    custom_type = schema.get("custom") or ""
    if custom_type and custom_type in JIRA_CUSTOM_TYPE_TO_TEMPLATE:
        return JIRA_CUSTOM_TYPE_TO_TEMPLATE[custom_type]

    schema_type = schema.get("type") or ""
    if schema_type in JIRA_SCHEMA_TYPE_TO_TEMPLATE:
        return JIRA_SCHEMA_TYPE_TO_TEMPLATE[schema_type]

    if field_data.get("custom"):
        return "custom"
    return "text"


def _metadata_audit_payload(metadata: JiraProjectMetadata) -> dict:
    return {
        "connection_id": str(metadata.connection_id),
        "metadata_id": str(metadata.id),
        "project_key": metadata.project_key,
        "status": metadata.status,
    }


def _get_or_create_metadata(connection) -> JiraProjectMetadata:
    metadata, created = JiraProjectMetadata.objects.get_or_create(
        connection=connection,
        defaults={
            "project_key": connection.project_key,
            "ttl_seconds": JIRA_METADATA_DEFAULT_TTL_SECONDS,
            "status": JiraSyncStatus.PENDING,
        },
    )
    if created:
        logger.info(
            "jira_metadata_created",
            connection_id=str(connection.id),
            metadata_id=str(metadata.id),
        )
    return metadata


def _prefetch_metadata(metadata: JiraProjectMetadata) -> JiraProjectMetadata:
    return (
        JiraProjectMetadata.objects.prefetch_related(
            "issue_types",
            "fields",
            "boards__sprints",
            "items",
        )
        .select_related("connection")
        .get(pk=metadata.pk)
    )


def get_metadata(*, workspace_id, connection_id, user: User) -> JiraProjectMetadata:
    connection = get_connection(workspace_id=workspace_id, connection_id=connection_id, user=user)
    require_membership(user=user, workspace=connection.workspace)
    metadata = _get_or_create_metadata(connection)
    return _prefetch_metadata(metadata)


def start_metadata_sync(*, workspace_id, connection_id, user: User) -> dict:
    connection = get_connection(workspace_id=workspace_id, connection_id=connection_id, user=user)
    _require_admin(user=user, workspace=connection.workspace, action="sync_metadata")

    if not connection.is_active:
        raise ApiError(
            detail="Cannot sync metadata for a deactivated Jira connection.",
            code="VALIDATION_ERROR",
            field_errors={"connection": ["Connection is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    metadata = _get_or_create_metadata(connection)
    if metadata.status == JiraSyncStatus.SYNCING:
        raise ApiError(
            detail="Metadata sync is already in progress.",
            code="SYNC_IN_PROGRESS",
            status_code=status.HTTP_409_CONFLICT,
        )

    metadata.status = JiraSyncStatus.SYNCING
    metadata.last_sync_started_at = timezone.now()
    metadata.last_error = ""
    metadata.save(update_fields=["status", "last_sync_started_at", "last_error", "updated_at"])

    from jira.tasks import sync_jira_metadata

    sync_jira_metadata.delay(str(connection.id))

    log_action(
        action="jira_metadata.sync.requested",
        entity_type="jira_project_metadata",
        entity_id=str(metadata.id),
        actor=user,
        payload=_metadata_audit_payload(metadata),
    )
    logger.info(
        "jira_metadata_sync_requested",
        connection_id=str(connection.id),
        metadata_id=str(metadata.id),
    )
    return {
        "status": JiraSyncStatus.SYNCING,
        "detail": "Metadata sync started.",
    }


@transaction.atomic
def _persist_metadata(metadata: JiraProjectMetadata, fetched: JiraMetadataFetchResult) -> None:
    JiraIssueType.objects.filter(metadata=metadata).delete()
    JiraField.objects.filter(metadata=metadata).delete()
    JiraBoard.objects.filter(metadata=metadata).delete()
    JiraMetadataItem.objects.filter(metadata=metadata).delete()

    issue_type_rows = [
        JiraIssueType(
            metadata=metadata,
            jira_id=str(item.get("id", "")),
            name=item.get("name", ""),
            hierarchy_level=item.get("hierarchyLevel"),
            is_subtask=bool(item.get("subtask")),
            description=item.get("description") or "",
            icon_url=item.get("iconUrl") or "",
        )
        for item in fetched.issue_types
        if item.get("id")
    ]
    if issue_type_rows:
        JiraIssueType.objects.bulk_create(issue_type_rows)

    field_rows = [
        JiraField(
            metadata=metadata,
            jira_id=str(item.get("id", "")),
            key=item.get("key", ""),
            name=item.get("name", ""),
            is_custom=bool(item.get("custom")),
            schema_type=(item.get("schema") or {}).get("type", ""),
            is_required=item.get("key", "") in fetched.required_field_keys,
            template_field_type=normalize_field_type(item),
            extra={"schema": item.get("schema") or {}},
        )
        for item in fetched.fields
        if item.get("key")
    ]
    if field_rows:
        JiraField.objects.bulk_create(field_rows)

    board_map: dict[str, JiraBoard] = {}
    for board in fetched.boards:
        board_obj = JiraBoard.objects.create(
            metadata=metadata,
            jira_board_id=board.board_id,
            name=board.name,
            board_type=board.board_type,
        )
        board_map[board.board_id] = board_obj

    sprint_rows: list[JiraSprint] = []
    for board_id, sprints in fetched.sprints_by_board.items():
        board_obj = board_map.get(board_id)
        if not board_obj:
            continue
        for sprint in sprints:
            sprint_rows.append(
                JiraSprint(
                    board=board_obj,
                    jira_sprint_id=sprint.sprint_id,
                    name=sprint.name,
                    state=sprint.state,
                    start_date=sprint.start_date,
                    end_date=sprint.end_date,
                    goal=sprint.goal,
                ),
            )
    if sprint_rows:
        JiraSprint.objects.bulk_create(sprint_rows)

    item_rows: list[JiraMetadataItem] = []
    for priority in fetched.priorities:
        item_rows.append(
            JiraMetadataItem(
                metadata=metadata,
                kind=JiraMetadataItemKind.PRIORITY,
                jira_id=str(priority.get("id", "")),
                name=priority.get("name", ""),
                extra={"iconUrl": priority.get("iconUrl", "")},
            ),
        )
    for status_item in fetched.statuses:
        item_rows.append(
            JiraMetadataItem(
                metadata=metadata,
                kind=JiraMetadataItemKind.STATUS,
                jira_id=str(status_item.get("id", "")),
                name=status_item.get("name", ""),
                extra={
                    "statusCategory": status_item.get("statusCategory") or {},
                },
            ),
        )
    for component in fetched.components:
        item_rows.append(
            JiraMetadataItem(
                metadata=metadata,
                kind=JiraMetadataItemKind.COMPONENT,
                jira_id=str(component.get("id", "")),
                name=component.get("name", ""),
                extra={"description": component.get("description") or ""},
            ),
        )
    for index, label in enumerate(fetched.labels):
        item_rows.append(
            JiraMetadataItem(
                metadata=metadata,
                kind=JiraMetadataItemKind.LABEL,
                jira_id=f"label-{index}",
                name=label,
                extra={},
            ),
        )
    if item_rows:
        JiraMetadataItem.objects.bulk_create(item_rows)


def run_metadata_sync(connection_id: str) -> None:
    from jira.models import JiraConnection

    started_at = time.monotonic()
    connection = JiraConnection.objects.select_related("workspace").get(pk=connection_id)
    metadata = _get_or_create_metadata(connection)

    logger.info(
        "jira_metadata_sync_started",
        connection_id=str(connection.id),
        metadata_id=str(metadata.id),
    )

    try:
        api_token = decrypt_secret(connection.api_token_encrypted)
        fetched = fetch_project_metadata(
            base_url=connection.base_url,
            email=connection.email,
            api_token=api_token,
            project_key=connection.project_key,
            board_id=connection.board_id or "",
        )
        with transaction.atomic():
            _persist_metadata(metadata, fetched)
            metadata.project_id = fetched.project.project_id
            metadata.project_name = fetched.project.project_name
            metadata.project_key = fetched.project.project_key
            metadata.status = JiraSyncStatus.FRESH
            metadata.fetched_at = timezone.now()
            metadata.last_error = ""
            metadata.save(
                update_fields=[
                    "project_id",
                    "project_name",
                    "project_key",
                    "status",
                    "fetched_at",
                    "last_error",
                    "updated_at",
                ],
            )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        payload = {
            **_metadata_audit_payload(metadata),
            "duration_ms": duration_ms,
            "issue_types_count": len(fetched.issue_types),
            "fields_count": len(fetched.fields),
            "boards_count": len(fetched.boards),
        }
        log_action(
            action="jira_metadata.sync.succeeded",
            entity_type="jira_project_metadata",
            entity_id=str(metadata.id),
            actor=None,
            payload=payload,
        )
        logger.info(
            "jira_metadata_sync_succeeded",
            connection_id=str(connection.id),
            metadata_id=str(metadata.id),
            duration_ms=duration_ms,
            issue_types_count=len(fetched.issue_types),
            fields_count=len(fetched.fields),
            boards_count=len(fetched.boards),
        )
    except (JiraAuthError, JiraClientError, Exception) as exc:
        error_message = str(exc) if str(exc) else "Metadata sync failed."
        JiraProjectMetadata.objects.filter(pk=metadata.pk).update(
            status=JiraSyncStatus.FAILED,
            last_error=error_message[:512],
            updated_at=timezone.now(),
        )
        metadata.refresh_from_db()

        http_status = getattr(exc, "status_code", None)
        log_action(
            action="jira_metadata.sync.failed",
            entity_type="jira_project_metadata",
            entity_id=str(metadata.id),
            actor=None,
            payload={
                **_metadata_audit_payload(metadata),
                "http_status": http_status,
                "error": error_message[:512],
            },
        )
        logger.warning(
            "jira_metadata_sync_failed",
            connection_id=str(connection.id),
            metadata_id=str(metadata.id),
            http_status=http_status,
            error=error_message[:512],
        )
        raise
