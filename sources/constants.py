"""Constants for source file upload and parsing."""
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


def get_max_file_size_bytes() -> int:
    return getattr(settings, "SOURCE_FILE_MAX_SIZE_BYTES", 10 * 1024 * 1024)


def get_preview_rows() -> int:
    return getattr(settings, "SOURCE_FILE_PREVIEW_ROWS", 20)
