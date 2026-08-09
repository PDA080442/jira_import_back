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
CSV_SNIFF_DELIMITERS = ",;\t|"
CSV_ENCODING_MIN_CONFIDENCE = 0.6

CSV_DELIMITER_CHOICES = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}
DELIMITER_TO_CHOICE = {v: k for k, v in CSV_DELIMITER_CHOICES.items()}

SUPPORTED_ENCODINGS = frozenset(
    {
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "cp1251",
        "windows-1251",
        "latin-1",
        "iso-8859-1",
        "ascii",
    },
)

# Parse warning codes returned to frontend in SourceFile.warnings
WARN_BOM_DETECTED = "BOM_DETECTED"
WARN_ENCODING_LOW_CONFIDENCE = "ENCODING_LOW_CONFIDENCE"
WARN_DECODE_REPLACED = "DECODE_REPLACED"
WARN_DELIMITER_GUESS_FAILED = "DELIMITER_GUESS_FAILED"
WARN_RAGGED_ROWS = "RAGGED_ROWS"
WARN_ENCODING_OVERRIDE_USED = "ENCODING_OVERRIDE_USED"
WARN_DELIMITER_OVERRIDE_USED = "DELIMITER_OVERRIDE_USED"


def resolve_delimiter_choice(choice: str) -> str:
    """Map API delimiter choice (comma/semicolon/tab/pipe) to character."""
    key = (choice or "").strip().lower()
    if key not in CSV_DELIMITER_CHOICES:
        raise ValueError(f"Unsupported delimiter: {choice}")
    return CSV_DELIMITER_CHOICES[key]


def normalize_encoding_name(encoding: str) -> str:
    value = (encoding or "").strip().lower()
    aliases = {
        "utf8": "utf-8",
        "utf-8-sig": "utf-8-sig",
        "windows-1251": "cp1251",
        "iso-8859-1": "latin-1",
    }
    return aliases.get(value, value)


def is_supported_encoding(encoding: str) -> bool:
    return normalize_encoding_name(encoding) in SUPPORTED_ENCODINGS


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


PRESET_MAX_NAME_LEN = 255
PRESET_SETTINGS_KEYS = frozenset(
    {
        "sheet",
        "header_row",
        "delimiter",
        "encoding",
        "selected_columns",
        "ignore_rows",
        "preview_rows",
    },
)
PRESET_FILE_ONLY_KEYS = frozenset({"delimiter", "encoding"})
PRESET_RECENT_DEFAULT_LIMIT = 10


def get_snapshot_max_rows() -> int:
    return getattr(settings, "SOURCE_SNAPSHOT_MAX_ROWS", 50_000)


def get_snapshot_retention_count() -> int:
    return getattr(settings, "SOURCE_SNAPSHOT_RETENTION_COUNT", 10)


def get_snapshot_retention_days() -> int:
    return getattr(settings, "SOURCE_SNAPSHOT_RETENTION_DAYS", 30)
