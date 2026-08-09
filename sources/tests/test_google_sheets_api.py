import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from sources.models import SourceParseStatus
from sources.services.google_sheets_client import FetchedWorksheet
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db

SAMPLE_SPREADSHEET_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
SAMPLE_URL = f"https://docs.google.com/spreadsheets/d/{SAMPLE_SPREADSHEET_ID}/edit"


def _list_url(workspace_id):
    return f"/api/workspaces/{workspace_id}/google-sheet-sources/"


def _detail_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/google-sheet-sources/{source_id}/"


def _deactivate_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/google-sheet-sources/{source_id}/deactivate/"


def _refresh_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/google-sheet-sources/{source_id}/refresh/"


@pytest.fixture
def editor_client():
    user = ActiveUserFactory(email="editor-gsheets@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def viewer_client():
    user = ActiveUserFactory(email="viewer-gsheets@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def test_create_google_source_returns_pending(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.refresh_google_sheet_snapshot.delay", lambda *a, **k: None)

    response = client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL, "name": "Backlog Sheet"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == SourceParseStatus.PENDING
    assert response.data["spreadsheet_id"] == SAMPLE_SPREADSHEET_ID
    assert response.data["name"] == "Backlog Sheet"


def test_create_rejects_invalid_url(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)

    response = client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": "not-a-valid-url"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"


def test_list_google_sources_for_member(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.refresh_google_sheet_snapshot.delay", lambda *a, **k: None)
    client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL},
        format="json",
    )

    response = client.get(_list_url(workspace.id))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


def test_non_member_gets_404(viewer_client, editor_client):
    viewer, _ = viewer_client
    _, owner = editor_client
    workspace = create_workspace_with_owner(user=owner)

    response = viewer.get(_list_url(workspace.id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_viewer_cannot_create(viewer_client, editor_client):
    viewer, viewer_user = viewer_client
    _, owner = editor_client
    workspace = create_workspace_with_owner(user=owner)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer_user,
        role=WorkspaceRole.VIEWER,
    )

    response = viewer.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_editor_can_deactivate(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.refresh_google_sheet_snapshot.delay", lambda *a, **k: None)

    created = client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL},
        format="json",
    )
    source_id = created.data["id"]

    response = client.post(_deactivate_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_active"] is False


def test_refresh_returns_202(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.refresh_google_sheet_snapshot.delay", lambda *a, **k: None)

    created = client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL},
        format="json",
    )
    source_id = created.data["id"]

    response = client.post(_refresh_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["status"] == SourceParseStatus.PENDING


def test_refresh_in_progress_returns_409(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.refresh_google_sheet_snapshot.delay", lambda *a, **k: None)

    created = client.post(
        _list_url(workspace.id),
        {"spreadsheet_url": SAMPLE_URL},
        format="json",
    )
    source_id = created.data["id"]

    from sources.models import GoogleSheetSource

    GoogleSheetSource.objects.filter(pk=source_id).update(status=SourceParseStatus.PARSING)

    response = client.post(_refresh_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "PARSE_IN_PROGRESS"
