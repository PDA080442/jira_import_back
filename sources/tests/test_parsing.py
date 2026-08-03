import pytest
from django.core.files.base import ContentFile

from sources.models import SourceFileType, SourceParseStatus
from sources.services.parsing import run_parse
from sources.tests.factories import (
    build_csv_bytes,
    build_xlsx_bytes,
    create_source_file,
    make_uploaded_csv,
    make_uploaded_xlsx,
)
from sources.services import files as files_service
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


def test_run_parse_xlsx_persists_sheets():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    upload = make_uploaded_xlsx()
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=upload,
        name="Backlog",
    )

    if source.status != SourceParseStatus.READY:
        run_parse(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.READY
    assert source.sheet_count >= 1
    sheet = source.sheets.first()
    assert sheet is not None
    assert sheet.column_count == 3
    assert len(sheet.columns) == 3
    assert len(sheet.preview_rows) >= 1


def test_run_parse_csv_detects_encoding_and_delimiter():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    csv_content = "Summary;Priority\nFix login;High\n"
    upload = make_uploaded_csv(content=csv_content)
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=upload,
    )
    if source.status != SourceParseStatus.READY:
        run_parse(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.READY
    assert source.file_type == SourceFileType.CSV
    assert source.encoding
    assert source.delimiter == ";"
    sheet = source.sheets.first()
    assert sheet.columns[0]["name"] == "Summary"


def test_run_parse_marks_failed_on_invalid_file():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    source = create_source_file(
        workspace=workspace,
        user=user,
        name="broken",
        file_type=SourceFileType.XLSX,
        status=SourceParseStatus.PENDING,
    )
    source.file.save("broken.xlsx", ContentFile(b"not-an-xlsx"), save=True)

    with pytest.raises(Exception):
        run_parse(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.FAILED
    assert source.error_message
