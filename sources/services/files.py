"""Source file CRUD and upload orchestration."""
import hashlib
import os
import uuid

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from rest_framework import status
from sources.constants import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    CSV_EXTENSIONS,
    EXCEL_EXTENSIONS,
    get_max_file_size_bytes,
    is_supported_encoding,
    normalize_encoding_name,
    resolve_delimiter_choice,
)
from sources.models import SourceFile, SourceFileType, SourceParseStatus
from sources.services.access import _require_editor, require_member
from tenants.services.workspace import get_workspace

logger = get_logger("sources.files")


def _source_audit_payload(source: SourceFile) -> dict:
    return {
        "source_file_id": str(source.id),
        "name": source.name,
        "file_type": source.file_type,
        "size_bytes": source.size_bytes,
        "status": source.status,
        "is_active": source.is_active,
        "sheet_count": source.sheet_count,
    }


def _resolve_encoding_override(encoding: str | None) -> str:
    if not encoding:
        return ""
    normalized = normalize_encoding_name(encoding)
    if not is_supported_encoding(normalized):
        raise ApiError(
            detail="Unsupported encoding.",
            code="VALIDATION_ERROR",
            field_errors={"encoding": [f"Supported encodings: utf-8, utf-8-sig, cp1251, latin-1, utf-16."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return normalized


def _resolve_delimiter_override(delimiter: str | None) -> str:
    if not delimiter:
        return ""
    try:
        return resolve_delimiter_choice(delimiter)
    except ValueError:
        raise ApiError(
            detail="Unsupported delimiter.",
            code="VALIDATION_ERROR",
            field_errors={"delimiter": ["Allowed values: comma, semicolon, tab, pipe."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from None


def _detect_file_type(filename: str) -> SourceFileType | None:
    ext = os.path.splitext(filename)[1].lower()
    if ext in EXCEL_EXTENSIONS:
        return SourceFileType.XLSX
    if ext in CSV_EXTENSIONS:
        return SourceFileType.CSV
    return None


def _validate_upload(*, upload, filename: str) -> SourceFileType:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError(
            detail="Unsupported file extension.",
            code="VALIDATION_ERROR",
            field_errors={"file": [f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    max_size = get_max_file_size_bytes()
    if upload.size > max_size:
        raise ApiError(
            detail="File is too large.",
            code="VALIDATION_ERROR",
            field_errors={"file": [f"Maximum file size is {max_size} bytes."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    content_type = getattr(upload, "content_type", "") or ""
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ApiError(
            detail="Unsupported content type.",
            code="VALIDATION_ERROR",
            field_errors={"file": [f"Unsupported content type: {content_type}."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_type = _detect_file_type(filename)
    if file_type is None:
        raise ApiError(
            detail="Unsupported file type.",
            code="VALIDATION_ERROR",
            field_errors={"file": ["Could not detect file type."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return file_type


def _compute_checksum(upload) -> str:
    hasher = hashlib.sha256()
    for chunk in upload.chunks():
        hasher.update(chunk)
    upload.seek(0)
    return hasher.hexdigest()


def list_source_files(*, workspace_id, user: User, include_inactive: bool = False):
    workspace = require_member(workspace_id=workspace_id, user=user)
    qs = SourceFile.objects.filter(workspace=workspace)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by("-created_at")


@transaction.atomic
def create_source_file(
    *,
    workspace_id,
    user: User,
    upload,
    name: str | None = None,
    delimiter: str | None = None,
    encoding: str | None = None,
) -> SourceFile:
    workspace = get_workspace(workspace_id=workspace_id, user=user)
    _require_editor(user=user, workspace=workspace, action="upload")

    filename = upload.name or "upload"
    file_type = _validate_upload(upload=upload, filename=filename)
    checksum = _compute_checksum(upload)
    delimiter_override = _resolve_delimiter_override(delimiter)
    encoding_override = _resolve_encoding_override(encoding)

    source_id = uuid.uuid4()
    source = SourceFile(
        id=source_id,
        workspace=workspace,
        name=name or os.path.splitext(os.path.basename(filename))[0],
        file_type=file_type,
        size_bytes=upload.size,
        content_type=getattr(upload, "content_type", "") or "",
        checksum=checksum,
        status=SourceParseStatus.PENDING,
        delimiter_override=delimiter_override,
        encoding_override=encoding_override,
        created_by=user,
    )
    source.file.save(os.path.basename(filename), upload, save=False)
    source.save()

    from sources.tasks import parse_source_file

    parse_source_file.delay(str(source.id))

    log_action(
        action="source_file.upload",
        entity_type="source_file",
        entity_id=str(source.id),
        actor=user,
        payload=_source_audit_payload(source),
    )
    logger.info(
        "source_file_uploaded",
        source_file_id=str(source.id),
        workspace_id=str(workspace.id),
        file_type=file_type,
        size_bytes=source.size_bytes,
    )
    return source


@transaction.atomic
def deactivate_source_file(*, source: SourceFile, user: User) -> SourceFile:
    _require_editor(user=user, workspace=source.workspace, action="deactivate")
    source.is_active = False
    source.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="source_file.deactivate",
        entity_type="source_file",
        entity_id=str(source.id),
        actor=user,
        payload=_source_audit_payload(source),
    )
    logger.info("source_file_deactivated", source_file_id=str(source.id))
    return source


def start_reparse(
    *,
    source: SourceFile,
    user: User,
    delimiter: str | None = None,
    encoding: str | None = None,
) -> dict:
    _require_editor(user=user, workspace=source.workspace, action="reparse")

    if not source.is_active:
        raise ApiError(
            detail="Cannot reparse a deactivated source file.",
            code="VALIDATION_ERROR",
            field_errors={"source_file": ["Source file is deactivated."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if source.status == SourceParseStatus.PARSING:
        raise ApiError(
            detail="Source file parsing is already in progress.",
            code="PARSE_IN_PROGRESS",
            status_code=status.HTTP_409_CONFLICT,
        )

    update_fields = ["status", "error_message", "updated_at"]
    if delimiter is not None:
        source.delimiter_override = _resolve_delimiter_override(delimiter) if delimiter else ""
        update_fields.append("delimiter_override")
    if encoding is not None:
        source.encoding_override = _resolve_encoding_override(encoding) if encoding else ""
        update_fields.append("encoding_override")

    source.status = SourceParseStatus.PENDING
    source.error_message = ""
    source.save(update_fields=update_fields)

    from sources.tasks import parse_source_file

    parse_source_file.delay(str(source.id))

    log_action(
        action="source_file.reparse.requested",
        entity_type="source_file",
        entity_id=str(source.id),
        actor=user,
        payload=_source_audit_payload(source),
    )
    logger.info("source_file_reparse_requested", source_file_id=str(source.id))
    return {
        "status": SourceParseStatus.PENDING,
        "detail": "Source file parsing started.",
    }
