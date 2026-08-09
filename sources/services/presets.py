"""Source preset CRUD, compatibility validation and apply."""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from rest_framework import status
from sources.constants import (
    PRESET_RECENT_DEFAULT_LIMIT,
    resolve_delimiter_choice,
)
from sources.models import (
    GoogleSheetSource,
    PresetBinding,
    PresetBindingStatus,
    PresetSourceType,
    SourceFile,
    SourceParseStatus,
    SourcePreset,
)
from sources.services.access import _require_editor, require_member
from tenants.services.workspace import get_workspace

logger = get_logger("sources.presets")


def _preset_audit_payload(preset: SourcePreset) -> dict:
    return {
        "preset_id": str(preset.id),
        "name": preset.name,
        "source_type": preset.source_type,
        "version": preset.version,
        "is_active": preset.is_active,
    }


def binding_is_stale(binding: PresetBinding) -> bool:
    if binding.preset_id is None:
        return False
    if binding.status == PresetBindingStatus.FAILED:
        return False
    preset = binding.preset
    if preset is None:
        return False
    return binding.applied_version != preset.version


def get_preset(*, workspace_id, preset_id, user: User) -> SourcePreset:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    try:
        return SourcePreset.objects.get(pk=preset_id, workspace=workspace)
    except SourcePreset.DoesNotExist as exc:
        raise ApiError(
            detail="Source preset not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc


def list_presets(
    *,
    workspace_id,
    user: User,
    source_type: str | None = None,
    include_inactive: bool = False,
):
    workspace = require_member(workspace_id=workspace_id, user=user)
    qs = SourcePreset.objects.filter(workspace=workspace)
    if source_type:
        qs = qs.filter(source_type=source_type)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by("-created_at")


def list_recent_configs(*, workspace_id, user: User, limit: int = PRESET_RECENT_DEFAULT_LIMIT):
    workspace = require_member(workspace_id=workspace_id, user=user)
    return (
        PresetBinding.objects.filter(workspace=workspace)
        .select_related("preset", "applied_by")
        .order_by("-last_applied_at", "-updated_at")[:limit]
    )


@transaction.atomic
def create_preset(
    *,
    workspace_id,
    user: User,
    name: str,
    source_type: str,
    settings: dict,
    description: str = "",
) -> SourcePreset:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    _require_editor(user=user, workspace=workspace, action="create_preset")

    if SourcePreset.objects.filter(
        workspace=workspace,
        source_type=source_type,
        name=name,
        is_active=True,
    ).exists():
        raise ApiError(
            detail="A preset with this name already exists.",
            code="VALIDATION_ERROR",
            field_errors={"name": ["Preset name must be unique within workspace and source type."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    preset = SourcePreset.objects.create(
        workspace=workspace,
        name=name,
        description=description or "",
        source_type=source_type,
        settings=settings or {},
        version=1,
        created_by=user,
    )
    log_action(
        action="source_preset.create",
        entity_type="source_preset",
        entity_id=str(preset.id),
        actor=user,
        payload=_preset_audit_payload(preset),
    )
    logger.info(
        "source_preset_created",
        preset_id=str(preset.id),
        workspace_id=str(workspace.id),
        source_type=source_type,
    )
    return preset


@transaction.atomic
def update_preset(
    *,
    preset: SourcePreset,
    user: User,
    name: str | None = None,
    description: str | None = None,
    settings: dict | None = None,
) -> SourcePreset:
    _require_editor(user=user, workspace=preset.workspace, action="update_preset")

    if not preset.is_active:
        raise ApiError(
            detail="Cannot update a deactivated preset.",
            code="VALIDATION_ERROR",
            field_errors={"preset": ["Preset is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    update_fields = ["updated_at"]
    if name is not None and name != preset.name:
        if SourcePreset.objects.filter(
            workspace=preset.workspace,
            source_type=preset.source_type,
            name=name,
            is_active=True,
        ).exclude(pk=preset.pk).exists():
            raise ApiError(
                detail="A preset with this name already exists.",
                code="VALIDATION_ERROR",
                field_errors={"name": ["Preset name must be unique within workspace and source type."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        preset.name = name
        update_fields.append("name")

    if description is not None:
        preset.description = description
        update_fields.append("description")

    if settings is not None and settings != preset.settings:
        preset.settings = settings
        preset.version += 1
        update_fields.extend(["settings", "version"])
        PresetBinding.objects.filter(preset=preset, status=PresetBindingStatus.APPLIED).update(
            status=PresetBindingStatus.STALE,
        )

    preset.save(update_fields=update_fields)
    log_action(
        action="source_preset.update",
        entity_type="source_preset",
        entity_id=str(preset.id),
        actor=user,
        payload=_preset_audit_payload(preset),
    )
    logger.info("source_preset_updated", preset_id=str(preset.id), version=preset.version)
    return preset


@transaction.atomic
def deactivate_preset(*, preset: SourcePreset, user: User) -> SourcePreset:
    _require_editor(user=user, workspace=preset.workspace, action="deactivate_preset")
    preset.is_active = False
    preset.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="source_preset.deactivate",
        entity_type="source_preset",
        entity_id=str(preset.id),
        actor=user,
        payload=_preset_audit_payload(preset),
    )
    logger.info("source_preset_deactivated", preset_id=str(preset.id))
    return preset


def _sheet_matches(sheet_spec: Any, *, name: str, index: int) -> bool:
    if sheet_spec is None:
        return True
    if isinstance(sheet_spec, int):
        return sheet_spec == index
    return str(sheet_spec).strip().lower() == name.strip().lower()


def _get_sheet_entries(source: SourceFile | GoogleSheetSource) -> list[dict]:
    if isinstance(source, SourceFile):
        return [
            {"name": s.name, "index": s.index, "columns": s.columns}
            for s in source.sheets.all()
        ]
    return [
        {"name": t.name, "index": t.index, "columns": t.columns}
        for t in source.tabs.all()
    ]


def _column_names(columns: list) -> set[str]:
    names = set()
    for col in columns or []:
        if isinstance(col, dict):
            name = col.get("name")
            if name:
                names.add(str(name))
        elif col:
            names.add(str(col))
    return names


def validate_preset_compatibility(
    preset: SourcePreset,
    *,
    source_type: str,
    source: SourceFile | GoogleSheetSource,
) -> None:
    if preset.source_type != source_type:
        raise ApiError(
            detail="Preset source type does not match the target source.",
            code="VALIDATION_ERROR",
            field_errors={
                "preset_id": [
                    f"Preset is for '{preset.source_type}' but source is '{source_type}'.",
                ],
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not preset.is_active:
        raise ApiError(
            detail="Cannot apply a deactivated preset.",
            code="VALIDATION_ERROR",
            field_errors={"preset_id": ["Preset is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    settings = preset.settings or {}
    if source.status != SourceParseStatus.READY:
        return

    sheet_spec = settings.get("sheet")
    selected_columns = settings.get("selected_columns") or []
    if not sheet_spec and not selected_columns:
        return

    entries = _get_sheet_entries(source)
    if sheet_spec is not None:
        matched = any(
            _sheet_matches(sheet_spec, name=e["name"], index=e["index"]) for e in entries
        )
        if not matched:
            raise ApiError(
                detail="Preset sheet/tab is not present in the source.",
                code="VALIDATION_ERROR",
                field_errors={
                    "settings.sheet": [f"Sheet/tab '{sheet_spec}' not found in source."],
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    if selected_columns:
        target_entry = None
        for entry in entries:
            if _sheet_matches(sheet_spec, name=entry["name"], index=entry["index"]):
                target_entry = entry
                break
        if target_entry is None and entries:
            target_entry = entries[0]
        if target_entry is None:
            return
        available = _column_names(target_entry["columns"])
        missing = [c for c in selected_columns if c not in available]
        if missing:
            raise ApiError(
                detail="Preset selected columns are not present in the source.",
                code="VALIDATION_ERROR",
                field_errors={
                    "settings.selected_columns": [
                        f"Columns not found: {', '.join(missing)}.",
                    ],
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )


def _push_preset_overrides_to_file(source: SourceFile, settings: dict) -> list[str]:
    update_fields = ["applied_preset", "applied_settings", "updated_at"]
    source.applied_settings = settings

    delimiter = settings.get("delimiter")
    if delimiter:
        source.delimiter_override = resolve_delimiter_choice(delimiter)
        update_fields.append("delimiter_override")
    encoding = settings.get("encoding")
    if encoding:
        source.encoding_override = encoding
        update_fields.append("encoding_override")
    return update_fields


def _push_preset_overrides_to_google(source: GoogleSheetSource, settings: dict) -> list[str]:
    update_fields = ["applied_preset", "applied_settings", "updated_at"]
    source.applied_settings = settings
    sheet = settings.get("sheet")
    if sheet is not None and not isinstance(sheet, int):
        source.worksheet_title = str(sheet)
        update_fields.append("worksheet_title")
    elif isinstance(sheet, str) and sheet:
        source.worksheet_title = sheet
        update_fields.append("worksheet_title")
    return update_fields


def _record_binding_failure(
    *,
    workspace,
    preset: SourcePreset,
    source_type: str,
    source_id,
    user: User,
    error_message: str,
    field_errors: dict,
) -> None:
    now = timezone.now()
    PresetBinding.objects.update_or_create(
        source_type=source_type,
        source_id=source_id,
        defaults={
            "workspace": workspace,
            "preset": preset,
            "applied_version": preset.version,
            "status": PresetBindingStatus.FAILED,
            "applied_settings": preset.settings or {},
            "last_applied_at": now,
            "last_error": error_message[:2000],
            "applied_by": user,
        },
    )
    log_action(
        action="source_preset.apply.failed",
        entity_type="source_preset",
        entity_id=str(preset.id),
        actor=user,
        payload={
            "preset_id": str(preset.id),
            "source_type": source_type,
            "source_id": str(source_id),
            "field_errors": field_errors,
        },
    )
    logger.warning(
        "source_preset_apply_failed",
        preset_id=str(preset.id),
        source_type=source_type,
        source_id=str(source_id),
        field_errors=field_errors,
    )


@transaction.atomic
def apply_preset_to_source(
    *,
    preset: SourcePreset,
    user: User,
    source_type: str,
    source: SourceFile | GoogleSheetSource,
) -> PresetBinding:
    _require_editor(user=user, workspace=source.workspace, action="apply_preset")

    if not source.is_active:
        raise ApiError(
            detail="Cannot apply preset to a deactivated source.",
            code="VALIDATION_ERROR",
            field_errors={"source": ["Source is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if source.status == SourceParseStatus.PARSING:
        raise ApiError(
            detail="Source processing is already in progress.",
            code="PARSE_IN_PROGRESS",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        validate_preset_compatibility(preset, source_type=source_type, source=source)
    except ApiError as exc:
        _record_binding_failure(
            workspace=source.workspace,
            preset=preset,
            source_type=source_type,
            source_id=source.id,
            user=user,
            error_message=exc.detail,
            field_errors=exc.field_errors or {},
        )
        raise

    settings = preset.settings or {}
    source.applied_preset = preset
    if source_type == PresetSourceType.FILE:
        update_fields = _push_preset_overrides_to_file(source, settings)
    else:
        update_fields = _push_preset_overrides_to_google(source, settings)
    source.save(update_fields=update_fields)

    now = timezone.now()
    binding, _created = PresetBinding.objects.update_or_create(
        source_type=source_type,
        source_id=source.id,
        defaults={
            "workspace": source.workspace,
            "preset": preset,
            "applied_version": preset.version,
            "status": PresetBindingStatus.APPLIED,
            "applied_settings": settings,
            "last_applied_at": now,
            "last_error": "",
            "applied_by": user,
        },
    )

    preset.last_applied_at = now
    preset.save(update_fields=["last_applied_at", "updated_at"])

    if source_type == PresetSourceType.FILE:
        from sources.tasks import parse_source_file

        source.status = SourceParseStatus.PENDING
        source.error_message = ""
        source.save(update_fields=["status", "error_message", "updated_at"])
        parse_source_file.delay(str(source.id), trigger="preset_apply", from_where="preset")
    else:
        from sources.tasks import refresh_google_sheet_snapshot

        source.status = SourceParseStatus.PENDING
        source.error_message = ""
        source.save(update_fields=["status", "error_message", "updated_at"])
        refresh_google_sheet_snapshot.delay(
            str(source.id),
            trigger="preset_apply",
            from_where="preset",
        )

    log_action(
        action="source_preset.apply",
        entity_type="source_preset",
        entity_id=str(preset.id),
        actor=user,
        payload={
            "preset_id": str(preset.id),
            "version": preset.version,
            "source_type": source_type,
            "source_id": str(source.id),
            "binding_id": str(binding.id),
        },
    )
    logger.info(
        "source_preset_applied",
        preset_id=str(preset.id),
        source_type=source_type,
        source_id=str(source.id),
        version=preset.version,
    )
    return binding


def resolve_preset_for_create(
    *,
    workspace_id,
    user: User,
    preset_id,
    expected_source_type: str,
) -> SourcePreset | None:
    if not preset_id:
        return None
    preset = get_preset(workspace_id=workspace_id, preset_id=preset_id, user=user)
    if preset.source_type != expected_source_type:
        raise ApiError(
            detail="Preset source type does not match the target source.",
            code="VALIDATION_ERROR",
            field_errors={"preset_id": ["Preset source type mismatch."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if not preset.is_active:
        raise ApiError(
            detail="Cannot use a deactivated preset.",
            code="VALIDATION_ERROR",
            field_errors={"preset_id": ["Preset is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return preset


def create_initial_binding(
    *,
    preset: SourcePreset,
    user: User,
    source_type: str,
    source_id,
    settings: dict,
) -> PresetBinding:
    now = timezone.now()
    binding = PresetBinding.objects.create(
        workspace=preset.workspace,
        preset=preset,
        source_type=source_type,
        source_id=source_id,
        applied_version=preset.version,
        status=PresetBindingStatus.APPLIED,
        applied_settings=settings,
        last_applied_at=now,
        applied_by=user,
    )
    preset.last_applied_at = now
    preset.save(update_fields=["last_applied_at", "updated_at"])
    return binding


def preset_settings_for_file_create(
    preset: SourcePreset,
    *,
    delimiter: str | None,
    encoding: str | None,
) -> tuple[str | None, str | None, dict]:
    """Return effective delimiter/encoding for create; explicit args win over preset."""
    settings = preset.settings or {}
    eff_delimiter = delimiter if delimiter is not None else settings.get("delimiter")
    eff_encoding = encoding if encoding is not None else settings.get("encoding")
    return eff_delimiter, eff_encoding, settings


def preset_worksheet_for_google_create(
    preset: SourcePreset,
    *,
    worksheet_title: str,
) -> str:
    if worksheet_title:
        return worksheet_title
    settings = preset.settings or {}
    sheet = settings.get("sheet")
    if sheet is not None and not isinstance(sheet, int):
        return str(sheet)
    return worksheet_title
