"""Tests for CSV encoding, delimiter detection, Excel normalization, and warnings."""
from datetime import datetime

import pytest
from django.core.files.base import ContentFile
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory

from sources.constants import (
    WARN_BOM_DETECTED,
    WARN_DELIMITER_OVERRIDE_USED,
    WARN_ENCODING_OVERRIDE_USED,
    WARN_RAGGED_ROWS,
)
from sources.models import SourceFileType, SourceParseStatus
from sources.services.parsing import _normalize_cell, _parse_csv, run_parse
from sources.tests.factories import (
    create_source_file,
    make_uploaded_csv,
)
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor_client():
    user = ActiveUserFactory(email="editor-encoding@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def test_parse_csv_utf8_bom_strips_header_and_warns():
    raw = b"\xef\xbb\xbfSummary;Priority\nFix login;High\n"
    sheets, encoding, delimiter, confidence, warnings = _parse_csv(raw)
    codes = [item["code"] for item in warnings]

    assert WARN_BOM_DETECTED in codes
    assert encoding in {"utf-8-sig", "utf-8"}
    assert delimiter == ";"
    assert sheets[0]["columns"][0]["name"] == "Summary"


def test_parse_csv_cp1251_cyrillic():
    text = "Имя;Значение\nТест;1\n"
    raw = text.encode("cp1251")
    sheets, encoding, _, _, warnings = _parse_csv(raw)

    assert sheets[0]["columns"][0]["name"] == "Имя"
    assert sheets[0]["preview_rows"][0][0] == "Тест"
    assert encoding


def test_parse_csv_auto_detects_semicolon_and_tab():
    semicolon_raw = "A;B\n1;2\n".encode("utf-8")
    _, _, semicolon, _, _ = _parse_csv(semicolon_raw)
    assert semicolon == ";"

    tab_raw = "A\tB\n1\t2\n".encode("utf-8")
    _, _, tab, _, _ = _parse_csv(tab_raw)
    assert tab == "\t"


def test_parse_csv_delimiter_override():
    raw = "A,B\n1,2\n".encode("utf-8")
    sheets, _, delimiter, _, warnings = _parse_csv(
        raw,
        delimiter_override=";",
    )
    codes = [item["code"] for item in warnings]

    assert WARN_DELIMITER_OVERRIDE_USED in codes
    assert delimiter == ";"
    assert sheets[0]["preview_rows"][0] == ["1,2"]


def test_parse_csv_encoding_override():
    text = "Имя;Значение\nТест;1\n"
    raw = text.encode("cp1251")
    _, encoding, _, _, warnings = _parse_csv(raw, encoding_override="cp1251")
    codes = [item["code"] for item in warnings]

    assert WARN_ENCODING_OVERRIDE_USED in codes
    assert encoding == "cp1251"


def test_parse_csv_ragged_rows_warning():
    raw = "A,B\n1,2,3\n4\n".encode("utf-8")
    _, _, _, _, warnings = _parse_csv(raw)
    codes = [item["code"] for item in warnings]
    assert WARN_RAGGED_ROWS in codes


def test_normalize_cell_excel_date_and_number():
    dt = datetime(2026, 7, 31, 15, 30, 0)
    assert _normalize_cell(dt) == "2026-07-31 15:30:00"
    assert _normalize_cell(42.0) == "42"
    assert _normalize_cell(True) == "true"
    assert _normalize_cell(False) == "false"


def test_run_parse_excel_normalizes_date_cell():
    workspace = create_workspace_with_owner()
    user = workspace.owner

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Due"])
    sheet.append([datetime(2026, 7, 31, 12, 0, 0)])
    from io import BytesIO

    buffer = BytesIO()
    workbook.save(buffer)

    source = create_source_file(
        workspace=workspace,
        user=user,
        name="dates",
        file_type=SourceFileType.XLSX,
        status=SourceParseStatus.PENDING,
    )
    source.file.save("dates.xlsx", ContentFile(buffer.getvalue()), save=True)
    run_parse(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.READY
    tab = source.sheets.first()
    assert tab.preview_rows[0][0] == "2026-07-31 12:00:00"


def test_api_detail_returns_warnings_after_bom_csv(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_args, **_kwargs: None)

    bom_csv = "\ufeffSummary;Priority\nFix login;High\n"
    upload = make_uploaded_csv(content=bom_csv)

    create_url = f"/api/workspaces/{workspace.id}/source-files/"
    response = client.post(create_url, {"file": upload}, format="multipart")
    assert response.status_code == status.HTTP_201_CREATED
    source_id = response.data["id"]

    from sources.models import SourceFile

    run_parse(str(source_id))

    detail_url = f"/api/workspaces/{workspace.id}/source-files/{source_id}/"
    detail = client.get(detail_url)
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["status"] == SourceParseStatus.READY
    assert detail.data["delimiter"] == ";"
    warning_codes = [item["code"] for item in detail.data["warnings"]]
    assert WARN_BOM_DETECTED in warning_codes


def test_reparse_with_delimiter_override(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_args, **_kwargs: None)

    upload = make_uploaded_csv(content="A,B\n1,2\n")
    create_url = f"/api/workspaces/{workspace.id}/source-files/"
    response = client.post(create_url, {"file": upload}, format="multipart")
    source_id = response.data["id"]

    from sources.models import SourceFile

    run_parse(str(source_id))
    source = SourceFile.objects.get(id=source_id)
    assert source.delimiter == ","

    reparse_url = f"/api/workspaces/{workspace.id}/source-files/{source_id}/reparse/"
    reparse = client.post(reparse_url, {"delimiter": "semicolon"}, format="json")
    assert reparse.status_code == status.HTTP_202_ACCEPTED

    source.refresh_from_db()
    assert source.delimiter_override == ";"
    run_parse(str(source.id))
    source.refresh_from_db()
    assert source.delimiter == ";"
