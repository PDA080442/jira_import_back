"""Fetch and persist Google Sheets snapshot (columns + preview)."""
import time

from django.db import transaction
from django.utils import timezone

from audit.services.log_action import log_action
from core.logging import get_logger
from sources.constants import get_preview_rows
from sources.models import GoogleSheetSource, GoogleSheetTab, SourceParseStatus
from sources.services.google_sheets import _google_source_audit_payload
from sources.services.google_sheets_client import (
    GoogleSheetsError,
    GoogleSheetsNotConfiguredError,
    fetch_spreadsheet,
)
from sources.services.parsing import _build_columns, _normalize_row

logger = get_logger("sources.google_snapshot")


def _worksheets_to_tabs(worksheets, preview_limit: int) -> list[dict]:
    tabs_data: list[dict] = []
    for index, ws in enumerate(worksheets):
        all_rows = [_normalize_row(row) for row in ws.values]
        if not all_rows:
            tabs_data.append(
                {
                    "index": index,
                    "name": ws.title,
                    "row_count": 0,
                    "column_count": 0,
                    "columns": [],
                    "preview_rows": [],
                },
            )
            continue

        header = all_rows[0]
        data_rows = all_rows[1:]
        columns = _build_columns(header)
        preview_rows = data_rows[:preview_limit]
        max_cols = max(len(header), max((len(row) for row in data_rows), default=0))
        tabs_data.append(
            {
                "index": index,
                "name": ws.title,
                "row_count": len(all_rows),
                "column_count": max_cols,
                "columns": columns,
                "preview_rows": preview_rows,
            },
        )
    return tabs_data


@transaction.atomic
def _persist_tabs(source: GoogleSheetSource, tabs_data: list[dict]) -> None:
    GoogleSheetTab.objects.filter(source=source).delete()
    rows = [
        GoogleSheetTab(
            source=source,
            index=item["index"],
            name=item["name"],
            row_count=item["row_count"],
            column_count=item["column_count"],
            columns=item["columns"],
            preview_rows=item["preview_rows"],
        )
        for item in tabs_data
    ]
    if rows:
        GoogleSheetTab.objects.bulk_create(rows)


def run_snapshot(source_id: str) -> None:
    started_at = time.monotonic()
    source = GoogleSheetSource.objects.select_related("workspace").get(pk=source_id)

    GoogleSheetSource.objects.filter(pk=source.pk).update(
        status=SourceParseStatus.PARSING,
        last_sync_started_at=timezone.now(),
        error_message="",
        updated_at=timezone.now(),
    )
    source.refresh_from_db()

    logger.info(
        "google_sheet_snapshot_started",
        google_sheet_source_id=str(source.id),
        spreadsheet_id=source.spreadsheet_id,
    )

    try:
        worksheets = fetch_spreadsheet(
            source.spreadsheet_id,
            worksheet_title=source.worksheet_title,
        )
        tabs_data = _worksheets_to_tabs(worksheets, get_preview_rows())

        with transaction.atomic():
            _persist_tabs(source, tabs_data)
            source.sheet_count = len(tabs_data)
            source.status = SourceParseStatus.READY
            source.synced_at = timezone.now()
            source.error_message = ""
            source.save(
                update_fields=[
                    "sheet_count",
                    "status",
                    "synced_at",
                    "error_message",
                    "updated_at",
                ],
            )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        payload = {
            **_google_source_audit_payload(source),
            "duration_ms": duration_ms,
            "tabs_count": source.sheet_count,
        }
        log_action(
            action="google_sheet_source.snapshot.succeeded",
            entity_type="google_sheet_source",
            entity_id=str(source.id),
            actor=None,
            payload=payload,
        )
        logger.info(
            "google_sheet_snapshot_succeeded",
            google_sheet_source_id=str(source.id),
            duration_ms=duration_ms,
            tabs_count=source.sheet_count,
        )
    except GoogleSheetsNotConfiguredError as exc:
        error_message = str(exc)
        GoogleSheetSource.objects.filter(pk=source.pk).update(
            status=SourceParseStatus.FAILED,
            error_message=error_message[:2000],
            updated_at=timezone.now(),
        )
        source.refresh_from_db()
        log_action(
            action="google_sheet_source.snapshot.failed",
            entity_type="google_sheet_source",
            entity_id=str(source.id),
            actor=None,
            payload={**_google_source_audit_payload(source), "error": error_message[:512]},
        )
        logger.warning(
            "google_sheet_snapshot_failed",
            google_sheet_source_id=str(source.id),
            error=error_message[:512],
        )
        raise
    except GoogleSheetsError as exc:
        error_message = str(exc) or "Google Sheet snapshot failed."
        GoogleSheetSource.objects.filter(pk=source.pk).update(
            status=SourceParseStatus.FAILED,
            error_message=error_message[:2000],
            updated_at=timezone.now(),
        )
        source.refresh_from_db()
        log_action(
            action="google_sheet_source.snapshot.failed",
            entity_type="google_sheet_source",
            entity_id=str(source.id),
            actor=None,
            payload={
                **_google_source_audit_payload(source),
                "http_status": exc.http_status,
                "error": error_message[:512],
            },
        )
        logger.warning(
            "google_sheet_snapshot_failed",
            google_sheet_source_id=str(source.id),
            http_status=exc.http_status,
            error=error_message[:512],
        )
        raise
    except Exception as exc:
        error_message = str(exc) if str(exc) else "Google Sheet snapshot failed."
        GoogleSheetSource.objects.filter(pk=source.pk).update(
            status=SourceParseStatus.FAILED,
            error_message=error_message[:2000],
            updated_at=timezone.now(),
        )
        source.refresh_from_db()
        log_action(
            action="google_sheet_source.snapshot.failed",
            entity_type="google_sheet_source",
            entity_id=str(source.id),
            actor=None,
            payload={**_google_source_audit_payload(source), "error": error_message[:512]},
        )
        logger.warning(
            "google_sheet_snapshot_failed",
            google_sheet_source_id=str(source.id),
            error=error_message[:512],
        )
        raise
