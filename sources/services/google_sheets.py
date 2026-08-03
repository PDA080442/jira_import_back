"""Google Sheets source CRUD and snapshot orchestration."""
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from rest_framework import status
from sources.constants import extract_spreadsheet_id
from sources.models import GoogleSheetSource, SourceParseStatus
from sources.services.access import _require_editor, require_member
from tenants.services.workspace import get_workspace

logger = get_logger("sources.google_sheets")


def _google_source_audit_payload(source: GoogleSheetSource) -> dict:
    return {
        "google_sheet_source_id": str(source.id),
        "name": source.name,
        "spreadsheet_id": source.spreadsheet_id,
        "worksheet_title": source.worksheet_title,
        "status": source.status,
        "is_active": source.is_active,
        "sheet_count": source.sheet_count,
    }


def _build_spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def list_google_sources(*, workspace_id, user: User, include_inactive: bool = False):
    workspace = require_member(workspace_id=workspace_id, user=user)
    qs = GoogleSheetSource.objects.filter(workspace=workspace)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by("-created_at")


@transaction.atomic
def create_google_source(
    *,
    workspace_id,
    user: User,
    spreadsheet_url: str,
    name: str | None = None,
    worksheet_title: str = "",
) -> GoogleSheetSource:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    _require_editor(user=user, workspace=workspace, action="create_google_sheet")

    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ApiError(
            detail="Invalid Google Sheets URL or spreadsheet ID.",
            code="VALIDATION_ERROR",
            field_errors={"spreadsheet_url": ["Could not extract spreadsheet ID."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    source = GoogleSheetSource.objects.create(
        workspace=workspace,
        name=name or f"Sheet {spreadsheet_id[:8]}",
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=_build_spreadsheet_url(spreadsheet_id),
        worksheet_title=worksheet_title or "",
        status=SourceParseStatus.PENDING,
        created_by=user,
    )

    from sources.tasks import refresh_google_sheet_snapshot

    refresh_google_sheet_snapshot.delay(str(source.id))

    log_action(
        action="google_sheet_source.create",
        entity_type="google_sheet_source",
        entity_id=str(source.id),
        actor=user,
        payload=_google_source_audit_payload(source),
    )
    logger.info(
        "google_sheet_source_created",
        google_sheet_source_id=str(source.id),
        workspace_id=str(workspace.id),
        spreadsheet_id=spreadsheet_id,
    )
    return source


@transaction.atomic
def deactivate_google_source(*, source: GoogleSheetSource, user: User) -> GoogleSheetSource:
    _require_editor(user=user, workspace=source.workspace, action="deactivate_google_sheet")
    source.is_active = False
    source.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="google_sheet_source.deactivate",
        entity_type="google_sheet_source",
        entity_id=str(source.id),
        actor=user,
        payload=_google_source_audit_payload(source),
    )
    logger.info("google_sheet_source_deactivated", google_sheet_source_id=str(source.id))
    return source


def start_snapshot_refresh(*, source: GoogleSheetSource, user: User) -> dict:
    _require_editor(user=user, workspace=source.workspace, action="refresh_google_sheet")

    if not source.is_active:
        raise ApiError(
            detail="Cannot refresh a deactivated Google Sheet source.",
            code="VALIDATION_ERROR",
            field_errors={"source": ["Source is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if source.status == SourceParseStatus.PARSING:
        raise ApiError(
            detail="Snapshot refresh is already in progress.",
            code="PARSE_IN_PROGRESS",
            status_code=status.HTTP_409_CONFLICT,
        )

    source.status = SourceParseStatus.PENDING
    source.error_message = ""
    source.save(update_fields=["status", "error_message", "updated_at"])

    from sources.tasks import refresh_google_sheet_snapshot

    refresh_google_sheet_snapshot.delay(str(source.id))

    log_action(
        action="google_sheet_source.refresh.requested",
        entity_type="google_sheet_source",
        entity_id=str(source.id),
        actor=user,
        payload=_google_source_audit_payload(source),
    )
    logger.info("google_sheet_source_refresh_requested", google_sheet_source_id=str(source.id))
    return {
        "status": SourceParseStatus.PENDING,
        "detail": "Google Sheet snapshot refresh started.",
    }
