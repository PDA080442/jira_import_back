"""Test factories for source files."""
import io

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from factory.django import DjangoModelFactory
from openpyxl import Workbook

from accounts.tests.factories import ActiveUserFactory
from sources.models import SourceFile, SourceFileType, SourceParseStatus, SourceSheet
from tenants.tests.factories import create_workspace_with_owner


class SourceFileFactory(DjangoModelFactory):
    class Meta:
        model = SourceFile

    workspace = factory.SubFactory("tenants.tests.factories.WorkspaceFactory")
    name = factory.Sequence(lambda n: f"Source {n}")
    file_type = SourceFileType.CSV
    size_bytes = 128
    content_type = "text/csv"
    checksum = factory.Sequence(lambda n: f"checksum-{n}")
    status = SourceParseStatus.PENDING
    created_by = factory.LazyAttribute(lambda o: o.workspace.owner)


class SourceSheetFactory(DjangoModelFactory):
    class Meta:
        model = SourceSheet

    source_file = factory.SubFactory(SourceFileFactory)
    index = 0
    name = "Sheet1"
    row_count = 10
    column_count = 3
    columns = factory.LazyFunction(
        lambda: [
            {"index": 0, "name": "Summary"},
            {"index": 1, "name": "Priority"},
            {"index": 2, "name": "Assignee"},
        ],
    )
    preview_rows = factory.LazyFunction(
        lambda: [
            ["Fix login", "High", "alex"],
            ["Add export", "Medium", "maria"],
        ],
    )


def build_xlsx_bytes(*, sheets=None) -> bytes:
    workbook = Workbook()
    default = workbook.active
    default.title = "Backlog"
    default.append(["Summary", "Priority", "Assignee"])
    default.append(["Fix login", "High", "alex"])
    default.append(["Add export", "Medium", "maria"])

    if sheets:
        workbook.remove(default)
        for title, rows in sheets:
            ws = workbook.create_sheet(title=title)
            for row in rows:
                ws.append(row)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_csv_bytes(content: str = "Summary,Priority\nFix login,High\nAdd export,Medium\n") -> bytes:
    return content.encode("utf-8")


def make_uploaded_xlsx(name: str = "backlog.xlsx") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        build_xlsx_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def make_uploaded_csv(name: str = "backlog.csv", content: str | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        build_csv_bytes(content or "Summary,Priority\nFix login,High\nAdd export,Medium\n"),
        content_type="text/csv",
    )


def create_source_file(*, workspace=None, user=None, **kwargs):
    user = user or ActiveUserFactory()
    workspace = workspace or create_workspace_with_owner(user=user)
    defaults = {
        "workspace": workspace,
        "created_by": user,
    }
    defaults.update(kwargs)
    return SourceFile.objects.create(**defaults)
