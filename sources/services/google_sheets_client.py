"""Google Sheets API client via global service account."""
import json
from dataclasses import dataclass

import gspread
from django.conf import settings
from google.oauth2 import service_account
from gspread.exceptions import APIError, SpreadsheetNotFound

from core.exceptions import ApiError
from rest_framework import status


class GoogleSheetsError(Exception):
    """Base error for Google Sheets operations."""

    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


class GoogleSheetsAuthError(GoogleSheetsError):
    pass


class GoogleSheetsNotFoundError(GoogleSheetsError):
    pass


class GoogleSheetsNotConfiguredError(GoogleSheetsError):
    pass


@dataclass
class FetchedWorksheet:
    title: str
    values: list[list[str]]


def _get_credentials():
    scopes = getattr(settings, "GOOGLE_SHEETS_SCOPES", [])
    file_path = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "") or ""
    json_str = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "") or ""

    if file_path:
        return service_account.Credentials.from_service_account_file(file_path, scopes=scopes)
    if json_str:
        info = json.loads(json_str)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    raise GoogleSheetsNotConfiguredError(
        "Google service account is not configured on the server.",
    )


def get_gspread_client():
    """Return authorized gspread client or raise ApiError if not configured."""
    try:
        credentials = _get_credentials()
    except GoogleSheetsNotConfiguredError as exc:
        raise ApiError(
            detail=str(exc),
            code="GOOGLE_NOT_CONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise ApiError(
            detail="Google service account configuration is invalid.",
            code="GOOGLE_NOT_CONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return gspread.authorize(credentials)


def _map_api_error(exc: APIError) -> GoogleSheetsError:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None) if response is not None else None
    message = str(exc) or "Google Sheets API error."
    if code == 403:
        return GoogleSheetsAuthError(
            "Access denied. Share the spreadsheet with the service account email.",
            http_status=403,
        )
    if code == 404:
        return GoogleSheetsNotFoundError("Spreadsheet not found.", http_status=404)
    return GoogleSheetsError(message, http_status=code)


def fetch_spreadsheet(
    spreadsheet_id: str,
    *,
    worksheet_title: str = "",
) -> list[FetchedWorksheet]:
    """Fetch worksheet values from Google Sheets."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
    except SpreadsheetNotFound as exc:
        raise GoogleSheetsNotFoundError("Spreadsheet not found.") from exc
    except APIError as exc:
        raise _map_api_error(exc) from exc
    except ApiError:
        raise
    except Exception as exc:
        raise GoogleSheetsError(str(exc) or "Failed to connect to Google Sheets.") from exc

    worksheets = spreadsheet.worksheets()
    if worksheet_title:
        worksheets = [ws for ws in worksheets if ws.title == worksheet_title]
        if not worksheets:
            raise GoogleSheetsNotFoundError(
                f'Worksheet "{worksheet_title}" not found in spreadsheet.',
            )

    result: list[FetchedWorksheet] = []
    for ws in worksheets:
        try:
            values = ws.get_all_values()
        except APIError as exc:
            raise _map_api_error(exc) from exc
        normalized = [[str(cell) if cell is not None else "" for cell in row] for row in values]
        result.append(FetchedWorksheet(title=ws.title, values=normalized))

    if not result:
        raise GoogleSheetsError("Spreadsheet contains no worksheets.")
    return result
