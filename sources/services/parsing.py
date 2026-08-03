"""Parse uploaded Excel/CSV files and persist sheet structure."""
import csv
import io
import time
from typing import Any

import chardet
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from audit.services.log_action import log_action
from core.logging import get_logger
from sources.constants import CSV_SNIFF_BYTES, get_preview_rows
from sources.models import SourceFile, SourceFileType, SourceParseStatus, SourceSheet
from sources.services.files import _source_audit_payload

logger = get_logger("sources.parsing")


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_row(row: list[Any]) -> list[str]:
    return [_cell_to_str(cell) for cell in row]


def _build_columns(header_row: list[str]) -> list[dict]:
    columns = []
    for index, name in enumerate(header_row):
        label = name.strip() if name else f"Column {index + 1}"
        columns.append({"index": index, "name": label})
    return columns


def _parse_xlsx(source: SourceFile, preview_limit: int) -> list[dict]:
    workbook = load_workbook(source.file.path, read_only=True, data_only=True)
    sheets_data: list[dict] = []

    try:
        for sheet_index, worksheet in enumerate(workbook.worksheets):
            rows_iter = worksheet.iter_rows(values_only=True)
            all_rows = [_normalize_row(row) for row in rows_iter]
            if not all_rows:
                sheets_data.append(
                    {
                        "index": sheet_index,
                        "name": worksheet.title,
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

            sheets_data.append(
                {
                    "index": sheet_index,
                    "name": worksheet.title,
                    "row_count": len(all_rows),
                    "column_count": max_cols,
                    "columns": columns,
                    "preview_rows": preview_rows,
                },
            )
    finally:
        workbook.close()

    if not sheets_data:
        raise ValueError("Excel file contains no worksheets.")
    return sheets_data


def _parse_csv(source: SourceFile, preview_limit: int) -> tuple[list[dict], str, str]:
    raw_bytes = source.file.read()
    source.file.seek(0)

    detected = chardet.detect(raw_bytes[:CSV_SNIFF_BYTES])
    encoding = detected.get("encoding") or "utf-8"
    text = raw_bytes.decode(encoding, errors="replace")

    sample = text[:CSV_SNIFF_BYTES]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows = [_normalize_row(row) for row in reader]
    if not all_rows:
        raise ValueError("CSV file is empty.")

    header = all_rows[0]
    data_rows = all_rows[1:]
    columns = _build_columns(header)
    preview_rows = data_rows[:preview_limit]
    max_cols = max(len(header), max((len(row) for row in data_rows), default=0))

    sheets_data = [
        {
            "index": 0,
            "name": source.name,
            "row_count": len(all_rows),
            "column_count": max_cols,
            "columns": columns,
            "preview_rows": preview_rows,
        },
    ]
    return sheets_data, encoding, delimiter


@transaction.atomic
def _persist_sheets(source: SourceFile, sheets_data: list[dict]) -> None:
    SourceSheet.objects.filter(source_file=source).delete()
    rows = [
        SourceSheet(
            source_file=source,
            index=item["index"],
            name=item["name"],
            row_count=item["row_count"],
            column_count=item["column_count"],
            columns=item["columns"],
            preview_rows=item["preview_rows"],
        )
        for item in sheets_data
    ]
    if rows:
        SourceSheet.objects.bulk_create(rows)


def run_parse(source_id: str) -> None:
    started_at = time.monotonic()
    source = SourceFile.objects.select_related("workspace").get(pk=source_id)

    SourceFile.objects.filter(pk=source.pk).update(
        status=SourceParseStatus.PARSING,
        parse_started_at=timezone.now(),
        error_message="",
        updated_at=timezone.now(),
    )
    source.refresh_from_db()

    logger.info(
        "source_file_parse_started",
        source_file_id=str(source.id),
        file_type=source.file_type,
    )

    preview_limit = get_preview_rows()
    encoding = ""
    delimiter = ""

    try:
        if source.file_type == SourceFileType.XLSX:
            sheets_data = _parse_xlsx(source, preview_limit)
        elif source.file_type == SourceFileType.CSV:
            sheets_data, encoding, delimiter = _parse_csv(source, preview_limit)
        else:
            raise ValueError(f"Unsupported file type: {source.file_type}")

        with transaction.atomic():
            _persist_sheets(source, sheets_data)
            source.sheet_count = len(sheets_data)
            source.encoding = encoding
            source.delimiter = delimiter
            source.status = SourceParseStatus.READY
            source.parsed_at = timezone.now()
            source.error_message = ""
            source.save(
                update_fields=[
                    "sheet_count",
                    "encoding",
                    "delimiter",
                    "status",
                    "parsed_at",
                    "error_message",
                    "updated_at",
                ],
            )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        payload = {
            **_source_audit_payload(source),
            "duration_ms": duration_ms,
            "sheets_count": source.sheet_count,
        }
        log_action(
            action="source_file.parse.succeeded",
            entity_type="source_file",
            entity_id=str(source.id),
            actor=None,
            payload=payload,
        )
        logger.info(
            "source_file_parse_succeeded",
            source_file_id=str(source.id),
            duration_ms=duration_ms,
            sheets_count=source.sheet_count,
        )
    except Exception as exc:
        error_message = str(exc) if str(exc) else "Source file parsing failed."
        SourceFile.objects.filter(pk=source.pk).update(
            status=SourceParseStatus.FAILED,
            error_message=error_message[:2000],
            updated_at=timezone.now(),
        )
        source.refresh_from_db()

        log_action(
            action="source_file.parse.failed",
            entity_type="source_file",
            entity_id=str(source.id),
            actor=None,
            payload={
                **_source_audit_payload(source),
                "error": error_message[:512],
            },
        )
        logger.warning(
            "source_file_parse_failed",
            source_file_id=str(source.id),
            error=error_message[:512],
        )
        raise
