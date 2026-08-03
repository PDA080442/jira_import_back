import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from sources.models import SourceParseStatus
from sources.tests.factories import make_uploaded_csv, make_uploaded_xlsx
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


def _list_url(workspace_id):
    return f"/api/workspaces/{workspace_id}/source-files/"


def _detail_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/source-files/{source_id}/"


def _deactivate_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/source-files/{source_id}/deactivate/"


def _reparse_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/source-files/{source_id}/reparse/"


@pytest.fixture
def editor_client():
    user = ActiveUserFactory(email="editor-sources@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def viewer_client():
    user = ActiveUserFactory(email="viewer-sources@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def test_upload_xlsx_returns_pending(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)

    def _noop_delay(source_id):
        return None

    monkeypatch.setattr("sources.tasks.parse_source_file.delay", _noop_delay)

    response = client.post(
        _list_url(workspace.id),
        {"file": make_uploaded_xlsx(), "name": "Backlog import"},
        format="multipart",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == SourceParseStatus.PENDING
    assert response.data["name"] == "Backlog import"
    assert response.data["file_type"] == "xlsx"


def test_upload_csv_returns_pending(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_: None)

    response = client.post(
        _list_url(workspace.id),
        {"file": make_uploaded_csv()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["file_type"] == "csv"


def test_upload_rejects_invalid_extension(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    bad_file = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")

    response = client.post(_list_url(workspace.id), {"file": bad_file}, format="multipart")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"


def test_list_source_files_for_member(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_: None)
    client.post(_list_url(workspace.id), {"file": make_uploaded_csv()}, format="multipart")

    response = client.get(_list_url(workspace.id))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


def test_non_member_gets_404(viewer_client, editor_client):
    viewer, _ = viewer_client
    _, owner = editor_client
    workspace = create_workspace_with_owner(user=owner)

    response = viewer.get(_list_url(workspace.id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_viewer_cannot_upload(viewer_client, editor_client):
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
        {"file": make_uploaded_csv()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_editor_can_deactivate(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_: None)

    upload = client.post(
        _list_url(workspace.id),
        {"file": make_uploaded_csv()},
        format="multipart",
    )
    source_id = upload.data["id"]

    response = client.post(_deactivate_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_active"] is False


def test_viewer_cannot_deactivate(viewer_client, editor_client, monkeypatch):
    viewer, viewer_user = viewer_client
    _, owner = editor_client
    workspace = create_workspace_with_owner(user=owner)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer_user,
        role=WorkspaceRole.VIEWER,
    )

    editor = APIClient()
    editor.force_authenticate(user=owner)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_: None)
    upload = editor.post(
        _list_url(workspace.id),
        {"file": make_uploaded_csv()},
        format="multipart",
    )
    source_id = upload.data["id"]

    response = viewer.post(_deactivate_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_reparse_returns_202(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_: None)

    upload = client.post(
        _list_url(workspace.id),
        {"file": make_uploaded_csv()},
        format="multipart",
    )
    source_id = upload.data["id"]

    response = client.post(_reparse_url(workspace.id, source_id))
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["status"] == SourceParseStatus.PENDING
