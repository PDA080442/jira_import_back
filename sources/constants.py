"""Constants for source file upload and parsing."""
import re

from django.conf import settings

ALLOWED_EXTENSIONS = {".xlsx", ".csv"}
EXCEL_EXTENSIONS = {".xlsx"}
CSV_EXTENSIONS = {".csv"}

ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
    "application/csv",
    "application/octet-stream",
}

CSV_SNIFF_BYTES = 65536

GOOGLE_SHEETS_URL_RE = re.compile(
    r"(?:https?://)?(?:docs\.google\.com/spreadsheets/d/|spreadsheets/d/)"
    r"([a-zA-Z0-9-_]+)",
)


def extract_spreadsheet_id(url_or_id: str) -> str | None:
    """Extract spreadsheet ID from Google Sheets URL or raw ID string."""
    value = (url_or_id or "").strip()
    if not value:
        return None
    match = GOOGLE_SHEETS_URL_RE.search(value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", value):
        return value
    return None


def get_max_file_size_bytes() -> int:
    return getattr(settings, "SOURCE_FILE_MAX_SIZE_BYTES", 10 * 1024 * 1024)


def get_preview_rows() -> int:
    return getattr(settings, "SOURCE_FILE_PREVIEW_ROWS", 20)
