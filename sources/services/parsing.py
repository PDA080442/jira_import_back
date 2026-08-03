"""Parse uploaded Excel/CSV files into SourceSheet rows."""
import csv
import io
from datetime import date, datetime, time
from typing import Any

import chardet
import openpyxl
import structlog
from django.db import transaction
from django.utils import timezone

from audit.services.log_action import log_action
from sources.constants import (
    CSV_ENCODING_MIN_CONFIDENCE,
    CSV_SNIFF_BYTES,
    CSV_SNIFF_DELIMITERS,
    WARN_BOM_DETECTED,
    WARN_DECODE_REPLACED,
    WARN_DELIMITER_GUESS_FAILED,
    WARN_DELIMITER_OVERRIDE_USED,
    WARN_ENCODING_LOW_CONFIDENCE,
    WARN_ENCODING_OVERRIDE_USED,
    WARN_RAGGED_ROWS,
    get_preview_rows,
)
from sources.models import SourceFile, SourceFileType, SourceParseStatus, SourceSheet

logger = structlog.get_logger(__name__)

BOM_UTF8_SIG = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


def _add_warning(warnings: list[dict], code: str, message: str) -> None:
    warnings.append({"code": code, "message": message})


def _detect_bom_encoding(raw_bytes: bytes) -> str | None:
    if raw_bytes.startswith(BOM_UTF8_SIG):
        return "utf-8-sig"
    if raw_bytes.startswith(BOM_UTF16_LE):
        return "utf-16-le"
    if raw_bytes.startswith(BOM_UTF16_BE):
        return "utf-16-be"
    return None


def _detect_encoding(
    raw_bytes: bytes,
    *,
    encoding_override: str,
    warnings: list[dict],
) -> tuple[str, float | None]:
    if encoding_override:
        _add_warning(
            warnings,
            WARN_ENCODING_OVERRIDE_USED,
            f"Using user-specified encoding: {encoding_override}.",
        )
        return encoding_override, None

    bom_encoding = _detect_bom_encoding(raw_bytes)
    if bom_encoding:
        _add_warning(warnings, WARN_BOM_DETECTED, f"BOM detected; using {bom_encoding}.")
        return bom_encoding, 1.0

    sample = raw_bytes[:CSV_SNIFF_BYTES]
    detected = chardet.detect(sample)
    encoding = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence")

    if confidence is not None and confidence < CSV_ENCODING_MIN_CONFIDENCE:
        _add_warning(
            warnings,
            WARN_ENCODING_LOW_CONFIDENCE,
            f"Encoding detection confidence is low ({confidence:.2f}); "
            f"detected {encoding}. Consider specifying encoding manually.",
        )

    return encoding, confidence


def _decode_csv_text(raw_bytes: bytes, encoding: str, warnings: list[dict]) -> str:
    text = raw_bytes.decode(encoding, errors="replace")
    if text.startswith("\ufeff"):
        _add_warning(warnings, WARN_BOM_DETECTED, "BOM detected in decoded text; stripped.")
        text = text.lstrip("\ufeff")
    replacement_count = text.count("\ufffd")
    if replacement_count:
        _add_warning(
            warnings,
            WARN_DECODE_REPLACED,
            f"{replacement_count} invalid character(s) replaced during decoding.",
        )
    return text


def _detect_delimiter(
    sample: str,
    *,
    delimiter_override: str,
    warnings: list[dict],
) -> str:
    if delimiter_override:
        _add_warning(
            warnings,
            WARN_DELIMITER_OVERRIDE_USED,
            f"Using user-specified delimiter: {repr(delimiter_override)}.",
        )
        return delimiter_override

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=CSV_SNIFF_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        _add_warning(
            warnings,
            WARN_DELIMITER_GUESS_FAILED,
            "Could not detect CSV delimiter; falling back to comma.",
        )
        return ","


def _check_ragged_rows(rows: list[list[str]], warnings: list[dict]) -> None:
    if len(rows) < 2:
        return
    expected = len(rows[0])
    ragged_count = sum(1 for row in rows[1:] if len(row) != expected)
    if ragged_count:
        _add_warning(
            warnings,
            WARN_RAGGED_ROWS,
            f"{ragged_count} row(s) have a different number of columns than the header.",
        )


def _normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


def _normalize_row(row: list[Any]) -> list[str]:
    return [_normalize_cell(cell) for cell in row]


def _build_columns(header: list[str]) -> list[dict]:
    columns = []
    for index, name in enumerate(header):
        columns.append({"index": index, "name": name or f"Column {index + 1}"})
    return columns


def _parse_csv(
    raw_bytes: bytes,
    *,
    encoding_override: str = "",
    delimiter_override: str = "",
) -> tuple[list[dict], str, str, float | None, list[dict]]:
    warnings: list[dict] = []
    encoding, confidence = _detect_encoding(
        raw_bytes,
        encoding_override=encoding_override,
        warnings=warnings,
    )
    text = _decode_csv_text(raw_bytes, encoding, warnings)

    sample = text[:CSV_SNIFF_BYTES]
    delimiter = _detect_delimiter(
        sample,
        delimiter_override=delimiter_override,
        warnings=warnings,
    )

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [_normalize_row(row) for row in reader]
    if not rows:
        return [], encoding, delimiter, confidence, warnings

    _check_ragged_rows(rows, warnings)

    header = rows[0]
    data_rows = rows[1:]
    columns = _build_columns(header)
    preview_limit = get_preview_rows()

    return (
        [
            {
                "index": 0,
                "name": "Sheet1",
                "row_count": len(data_rows),
                "column_count": len(columns),
                "columns": columns,
                "preview_rows": data_rows[:preview_limit],
            }
        ],
        encoding,
        delimiter,
        confidence,
        warnings,
    )


def _parse_xlsx(raw_bytes: bytes) -> tuple[list[dict], list[dict]]:
    warnings: list[dict] = []
    workbook = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
    preview_limit = get_preview_rows()
    sheets_data = []

    try:
        for sheet_index, worksheet in enumerate(workbook.worksheets):
            rows_raw = list(worksheet.iter_rows(values_only=True))
            if not rows_raw:
                continue

            rows = [_normalize_row(list(row)) for row in rows_raw]
            header = rows[0]
            data_rows = rows[1:]
            columns = _build_columns(header)

            if data_rows:
                expected = len(header)
                ragged_count = sum(1 for row in data_rows if len(row) != expected)
                if ragged_count:
                    _add_warning(
                        warnings,
                        WARN_RAGGED_ROWS,
                        f"Sheet '{worksheet.title}': {ragged_count} row(s) "
                        f"have a different number of columns than the header.",
                    )

            sheets_data.append(
                {
                    "index": sheet_index,
                    "name": worksheet.title,
                    "row_count": len(data_rows),
                    "column_count": len(columns),
                    "columns": columns,
                    "preview_rows": data_rows[:preview_limit],
                }
            )
    finally:
        workbook.close()

    return sheets_data, warnings


@transaction.atomic
def _persist_sheets(
    source: SourceFile,
    sheets_data: list[dict],
    *,
    encoding: str = "",
    delimiter: str = "",
    encoding_confidence: float | None = None,
    warnings: list[dict] | None = None,
) -> None:
    source.sheets.all().delete()
    for sheet_data in sheets_data:
        SourceSheet.objects.create(
            source_file=source,
            index=sheet_data["index"],
            name=sheet_data["name"],
            row_count=sheet_data["row_count"],
            column_count=sheet_data["column_count"],
            columns=sheet_data["columns"],
            preview_rows=sheet_data["preview_rows"],
        )

    source.sheet_count = len(sheets_data)
    source.encoding = encoding
    source.delimiter = delimiter
    source.encoding_confidence = encoding_confidence
    source.warnings = warnings or []
    source.status = SourceParseStatus.READY
    source.error_message = ""
    source.parsed_at = timezone.now()
    source.save(
        update_fields=[
            "sheet_count",
            "encoding",
            "delimiter",
            "encoding_confidence",
            "warnings",
            "status",
            "error_message",
            "parsed_at",
            "updated_at",
        ]
    )


def run_parse(source_file_id: str) -> None:
    """Parse source file and persist sheets. Called from Celery task."""
    source = SourceFile.objects.select_for_update().get(id=source_file_id)

    source.status = SourceParseStatus.PARSING
    source.parse_started_at = timezone.now()
    source.error_message = ""
    source.save(update_fields=["status", "parse_started_at", "error_message", "updated_at"])

    try:
        with source.file.open("rb") as handle:
            raw_bytes = handle.read()

        encoding = ""
        delimiter = ""
        encoding_confidence: float | None = None
        warnings: list[dict] = []

        if source.file_type == SourceFileType.CSV:
            sheets_data, encoding, delimiter, encoding_confidence, warnings = _parse_csv(
                raw_bytes,
                encoding_override=source.encoding_override,
                delimiter_override=source.delimiter_override,
            )
        elif source.file_type == SourceFileType.XLSX:
            sheets_data, warnings = _parse_xlsx(raw_bytes)
        else:
            raise ValueError(f"Unsupported file type: {source.file_type}")

        _persist_sheets(
            source,
            sheets_data,
            encoding=encoding,
            delimiter=delimiter,
            encoding_confidence=encoding_confidence,
            warnings=warnings,
        )

        warnings_count = len(warnings)
        log_action(
            action="source_file.parse.succeeded",
            entity_type="source_file",
            entity_id=str(source.id),
            actor=source.created_by,
            payload={
                "source_file_id": str(source.id),
                "sheet_count": source.sheet_count,
                "file_type": source.file_type,
                "encoding": encoding,
                "delimiter": delimiter,
                "encoding_confidence": encoding_confidence,
                "warnings_count": warnings_count,
            },
        )
        log_kwargs = {
            "source_file_id": str(source.id),
            "sheet_count": source.sheet_count,
            "warnings_count": warnings_count,
        }
        if warnings_count:
            logger.warning("source_file_parse_warnings", warnings=warnings, **log_kwargs)
        else:
            logger.info("source_file_parsed", **log_kwargs)

    except Exception as exc:
        source.status = SourceParseStatus.FAILED
        source.error_message = str(exc)[:2000]
        source.parsed_at = timezone.now()
        source.save(update_fields=["status", "error_message", "parsed_at", "updated_at"])
        log_action(
            action="source_file.parse.failed",
            entity_type="source_file",
            entity_id=str(source.id),
            actor=source.created_by,
            payload={
                "source_file_id": str(source.id),
                "error": source.error_message,
            },
        )
        logger.exception("source_file_parse_failed", source_file_id=str(source.id))
        raise
