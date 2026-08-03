import pytest

from sources.models import SourceParseStatus
from sources.services.google_sheets_client import FetchedWorksheet
from sources.services.google_snapshot import run_snapshot
from sources.tests.factories import create_google_sheet_source
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


def test_run_snapshot_persists_tabs(monkeypatch):
    workspace = create_workspace_with_owner()
    user = workspace.owner
    source = create_google_sheet_source(workspace=workspace, user=user)

    def _mock_fetch(spreadsheet_id, *, worksheet_title=""):
        return [
            FetchedWorksheet(
                title="Backlog",
                values=[
                    ["Summary", "Priority"],
                    ["Fix login", "High"],
                    ["Add export", "Medium"],
                ],
            ),
        ]

    monkeypatch.setattr("sources.services.google_snapshot.fetch_spreadsheet", _mock_fetch)

    run_snapshot(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.READY
    assert source.sheet_count == 1
    tab = source.tabs.first()
    assert tab is not None
    assert tab.name == "Backlog"
    assert len(tab.columns) == 2
    assert len(tab.preview_rows) >= 1


def test_run_snapshot_marks_failed_on_error(monkeypatch):
    workspace = create_workspace_with_owner()
    user = workspace.owner
    source = create_google_sheet_source(workspace=workspace, user=user)

    def _mock_fetch(*args, **kwargs):
        from sources.services.google_sheets_client import GoogleSheetsAuthError

        raise GoogleSheetsAuthError("Access denied.")

    monkeypatch.setattr("sources.services.google_snapshot.fetch_spreadsheet", _mock_fetch)

    with pytest.raises(Exception):
        run_snapshot(str(source.id))

    source.refresh_from_db()
    assert source.status == SourceParseStatus.FAILED
    assert "Access denied" in source.error_message
