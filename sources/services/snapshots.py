"""Source snapshot creation, compare, resolve and retention cleanup."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from deepdiff import DeepDiff
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from sources.constants import (
    get_snapshot_max_rows,
    get_snapshot_retention_count,
    get_snapshot_retention_days,
)
from sources.models import (
    GoogleSheetSource,
    PresetSourceType,
    RefreshRunStatus,
    RefreshTrigger,
    SourceFile,
    SourceRefreshRun,
    SourceSnapshot,
)
from sources.services.access import require_member
from tenants.models import Workspace

logger = get_logger("sources.snapshots")


def _canonical_checksum(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_snapshot_payload(sheets_full: list[dict]) -> tuple[dict, int, bool]:
    """Build snapshot data from full sheet dicts (may include rows + preview_rows)."""
    max_rows = get_snapshot_max_rows()
    sheets_out: list[dict] = []
    total_rows = 0
    truncated = False
    remaining = max_rows

    for sheet in sheets_full:
        rows = sheet.get("rows")
        if rows is None:
            rows = sheet.get("preview_rows") or []
        if remaining <= 0:
            truncated = True
            kept_rows: list = []
        elif len(rows) > remaining:
            truncated = True
            kept_rows = rows[:remaining]
            remaining = 0
        else:
            kept_rows = list(rows)
            remaining -= len(kept_rows)

        columns = sheet.get("columns") or []
        sheets_out.append(
            {
                "index": sheet.get("index", 0),
                "name": sheet.get("name") or "Sheet1",
                "columns": columns,
                "rows": kept_rows,
                "row_count": len(kept_rows),
                "column_count": sheet.get("column_count") or len(columns),
            },
        )
        total_rows += len(kept_rows)

    return {"sheets": sheets_out}, total_rows, truncated


def _set_source_active_snapshot(
    *,
    source_type: str,
    source_id,
    snapshot: SourceSnapshot,
) -> None:
    if source_type == PresetSourceType.FILE:
        SourceFile.objects.filter(pk=source_id).update(
            active_snapshot=snapshot,
            updated_at=timezone.now(),
        )
    elif source_type == PresetSourceType.GOOGLE:
        GoogleSheetSource.objects.filter(pk=source_id).update(
            active_snapshot=snapshot,
            updated_at=timezone.now(),
        )


@transaction.atomic
def create_snapshot_after_success(
    *,
    workspace: Workspace,
    source_type: str,
    source_id,
    sheets_full: list[dict],
    user: User | None = None,
    trigger: str = RefreshTrigger.PARSE,
    from_where: str = "",
    meta: dict | None = None,
    started_at=None,
) -> tuple[SourceSnapshot, SourceRefreshRun]:
    started = started_at or timezone.now()
    data, row_count, truncated = build_snapshot_payload(sheets_full)
    checksum = _canonical_checksum(data)

    SourceSnapshot.objects.filter(
        source_type=source_type,
        source_id=source_id,
        is_active=True,
    ).update(is_active=False, updated_at=timezone.now())

    snapshot = SourceSnapshot.objects.create(
        workspace=workspace,
        source_type=source_type,
        source_id=source_id,
        data=data,
        row_count=row_count,
        sheet_count=len(data.get("sheets") or []),
        checksum=checksum,
        is_active=True,
        is_truncated=truncated,
        created_by=user,
    )
    _set_source_active_snapshot(
        source_type=source_type,
        source_id=source_id,
        snapshot=snapshot,
    )

    run_status = RefreshRunStatus.TRUNCATED if truncated else RefreshRunStatus.SUCCEEDED
    run_meta = dict(meta or {})
    run_meta["truncated"] = truncated
    run_meta["row_count"] = row_count

    refresh_run = SourceRefreshRun.objects.create(
        workspace=workspace,
        source_type=source_type,
        source_id=source_id,
        snapshot=snapshot,
        triggered_by=user,
        trigger=trigger,
        status=run_status,
        from_where=from_where or "",
        started_at=started,
        finished_at=timezone.now(),
        meta=run_meta,
    )

    log_action(
        action="source_snapshot.created",
        entity_type="source_snapshot",
        entity_id=str(snapshot.id),
        actor=user,
        payload={
            "snapshot_id": str(snapshot.id),
            "source_type": source_type,
            "source_id": str(source_id),
            "row_count": row_count,
            "sheet_count": snapshot.sheet_count,
            "is_truncated": truncated,
            "refresh_run_id": str(refresh_run.id),
        },
    )
    log_action(
        action="source_refresh_run.succeeded",
        entity_type="source_refresh_run",
        entity_id=str(refresh_run.id),
        actor=user,
        payload={
            "refresh_run_id": str(refresh_run.id),
            "status": run_status,
            "trigger": trigger,
            "source_type": source_type,
            "source_id": str(source_id),
            "snapshot_id": str(snapshot.id),
        },
    )
    logger.info(
        "source_snapshot_created",
        snapshot_id=str(snapshot.id),
        source_type=source_type,
        source_id=str(source_id),
        row_count=row_count,
        truncated=truncated,
    )
    return snapshot, refresh_run


def record_refresh_failure(
    *,
    workspace: Workspace,
    source_type: str,
    source_id,
    user: User | None = None,
    trigger: str = RefreshTrigger.PARSE,
    from_where: str = "",
    error_message: str = "",
    meta: dict | None = None,
    started_at=None,
) -> SourceRefreshRun:
    started = started_at or timezone.now()
    refresh_run = SourceRefreshRun.objects.create(
        workspace=workspace,
        source_type=source_type,
        source_id=source_id,
        snapshot=None,
        triggered_by=user,
        trigger=trigger,
        status=RefreshRunStatus.FAILED,
        from_where=from_where or "",
        error_message=(error_message or "")[:2000],
        started_at=started,
        finished_at=timezone.now(),
        meta=meta or {},
    )
    log_action(
        action="source_refresh_run.failed",
        entity_type="source_refresh_run",
        entity_id=str(refresh_run.id),
        actor=user,
        payload={
            "refresh_run_id": str(refresh_run.id),
            "source_type": source_type,
            "source_id": str(source_id),
            "error": refresh_run.error_message[:512],
        },
    )
    logger.warning(
        "source_refresh_run_failed",
        refresh_run_id=str(refresh_run.id),
        source_type=source_type,
        source_id=str(source_id),
    )
    return refresh_run


def list_refresh_runs(*, workspace_id, user: User, source_type: str, source_id):
    require_member(workspace_id=workspace_id, user=user)
    return SourceRefreshRun.objects.filter(
        workspace_id=workspace_id,
        source_type=source_type,
        source_id=source_id,
    ).select_related("snapshot", "triggered_by")


def list_snapshots(*, workspace_id, user: User, source_type: str, source_id):
    require_member(workspace_id=workspace_id, user=user)
    return SourceSnapshot.objects.filter(
        workspace_id=workspace_id,
        source_type=source_type,
        source_id=source_id,
    )


def get_snapshot(*, workspace_id, user: User, source_type: str, source_id, snapshot_id) -> SourceSnapshot:
    require_member(workspace_id=workspace_id, user=user)
    try:
        return SourceSnapshot.objects.get(
            pk=snapshot_id,
            workspace_id=workspace_id,
            source_type=source_type,
            source_id=source_id,
        )
    except SourceSnapshot.DoesNotExist as exc:
        raise ApiError(
            detail="Source snapshot not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc


def get_active_snapshot(*, source_type: str, source_id) -> SourceSnapshot | None:
    return SourceSnapshot.objects.filter(
        source_type=source_type,
        source_id=source_id,
        is_active=True,
    ).first()


def resolve_snapshot_for_job(
    *,
    source_type: str,
    source_id,
    snapshot_id=None,
) -> SourceSnapshot:
    """Resolve snapshot for future dry-run/publish. Prefer explicit id, else active."""
    if snapshot_id:
        try:
            return SourceSnapshot.objects.get(
                pk=snapshot_id,
                source_type=source_type,
                source_id=source_id,
            )
        except SourceSnapshot.DoesNotExist as exc:
            raise ApiError(
                detail="Source snapshot not found for this source.",
                code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            ) from exc

    active = get_active_snapshot(source_type=source_type, source_id=source_id)
    if active is None:
        raise ApiError(
            detail="No active source snapshot. Parse or refresh the source first.",
            code="VALIDATION_ERROR",
            field_errors={"snapshot_id": ["No active snapshot available."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return active


def _column_names(columns: list) -> set[str]:
    names: set[str] = set()
    for col in columns or []:
        if isinstance(col, dict) and col.get("name"):
            names.add(str(col["name"]))
        elif col:
            names.add(str(col))
    return names


def compare_snapshots(current: SourceSnapshot, previous: SourceSnapshot) -> dict[str, Any]:
    current_sheets = (current.data or {}).get("sheets") or []
    previous_sheets = (previous.data or {}).get("sheets") or []

    current_by_name = {s.get("name"): s for s in current_sheets}
    previous_by_name = {s.get("name"): s for s in previous_sheets}

    sheets_added = sorted(set(current_by_name) - set(previous_by_name))
    sheets_removed = sorted(set(previous_by_name) - set(current_by_name))
    shared = set(current_by_name) & set(previous_by_name)

    columns_added: list[str] = []
    columns_removed: list[str] = []
    changed_cells = 0
    max_cell_samples = 500

    for name in shared:
        cur = current_by_name[name]
        prev = previous_by_name[name]
        cur_cols = _column_names(cur.get("columns"))
        prev_cols = _column_names(prev.get("columns"))
        columns_added.extend(sorted(cur_cols - prev_cols))
        columns_removed.extend(sorted(prev_cols - cur_cols))

        cur_rows = cur.get("rows") or []
        prev_rows = prev.get("rows") or []
        # Cap deepdiff work on overlapping prefix
        limit = min(len(cur_rows), len(prev_rows), 200)
        if limit:
            diff = DeepDiff(
                prev_rows[:limit],
                cur_rows[:limit],
                ignore_order=False,
                view="text",
            )
            # Count changed values roughly from values_changed / iterable_item_*
            for key in ("values_changed", "iterable_item_added", "iterable_item_removed"):
                part = diff.get(key) or {}
                changed_cells += min(len(part), max_cell_samples)
                if changed_cells >= max_cell_samples:
                    break
        changed_cells += abs(len(cur_rows) - len(prev_rows))

    return {
        "current_id": str(current.id),
        "previous_id": str(previous.id),
        "summary": {
            "row_count_delta": current.row_count - previous.row_count,
            "sheet_count_delta": current.sheet_count - previous.sheet_count,
            "sheets_added": sheets_added,
            "sheets_removed": sheets_removed,
            "columns_added": sorted(set(columns_added)),
            "columns_removed": sorted(set(columns_removed)),
            "changed_cells_estimate": changed_cells,
            "current_truncated": current.is_truncated,
            "previous_truncated": previous.is_truncated,
        },
    }


def compare_for_source(
    *,
    workspace_id,
    user: User,
    source_type: str,
    source_id,
    current_id=None,
    previous_id=None,
) -> dict:
    require_member(workspace_id=workspace_id, user=user)
    qs = SourceSnapshot.objects.filter(
        workspace_id=workspace_id,
        source_type=source_type,
        source_id=source_id,
    ).order_by("-created_at")

    if current_id:
        current = get_snapshot(
            workspace_id=workspace_id,
            user=user,
            source_type=source_type,
            source_id=source_id,
            snapshot_id=current_id,
        )
    else:
        current = qs.filter(is_active=True).first() or qs.first()
        if current is None:
            raise ApiError(
                detail="No snapshots available to compare.",
                code="VALIDATION_ERROR",
                field_errors={"current": ["No snapshots found."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    if previous_id:
        previous = get_snapshot(
            workspace_id=workspace_id,
            user=user,
            source_type=source_type,
            source_id=source_id,
            snapshot_id=previous_id,
        )
    else:
        previous = (
            qs.exclude(pk=current.pk)
            .filter(created_at__lt=current.created_at)
            .order_by("-created_at")
            .first()
        )
        if previous is None:
            raise ApiError(
                detail="No previous snapshot available to compare.",
                code="VALIDATION_ERROR",
                field_errors={"previous": ["Need at least two snapshots."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    return compare_snapshots(current, previous)


@transaction.atomic
def cleanup_old_snapshots() -> dict:
    """Hard-delete inactive snapshots outside retention count/days. Keeps active."""
    retention_count = get_snapshot_retention_count()
    retention_days = get_snapshot_retention_days()
    cutoff = timezone.now() - timedelta(days=retention_days)

    deleted_total = 0
    pairs = (
        SourceSnapshot.objects.filter(is_active=False)
        .values_list("source_type", "source_id")
        .distinct()
    )
    for source_type, source_id in pairs:
        keep_ids = list(
            SourceSnapshot.objects.filter(
                source_type=source_type,
                source_id=source_id,
                is_active=False,
            )
            .order_by("-created_at")
            .values_list("id", flat=True)[:retention_count]
        )
        delete_qs = SourceSnapshot.objects.filter(
            source_type=source_type,
            source_id=source_id,
            is_active=False,
        ).filter(Q(~Q(id__in=keep_ids)) | Q(created_at__lt=cutoff))
        count, _ = delete_qs.delete()
        deleted_total += count

    log_action(
        action="source_snapshot.cleanup",
        entity_type="source_snapshot",
        entity_id="",
        actor=None,
        payload={"deleted_count": deleted_total},
    )
    logger.info("source_snapshot_cleanup", deleted_count=deleted_total)
    return {"deleted_count": deleted_total}
