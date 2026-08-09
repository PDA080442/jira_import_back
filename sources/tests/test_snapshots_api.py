"""API tests for source snapshots and refresh history."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from sources.services.parsing import run_parse
from sources.tests.factories import make_uploaded_csv
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor_client(monkeypatch):
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *a, **k: None)
    user = ActiveUserFactory(email="editor-snap@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def test_snapshots_history_and_compare(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    upload = make_uploaded_csv(content="Summary,Priority\nFix,High\n")
    created = client.post(
        f"/api/workspaces/{workspace.id}/source-files/",
        {"file": upload},
        format="multipart",
    )
    assert created.status_code == status.HTTP_201_CREATED
    source_id = created.data["id"]
    run_parse(str(source_id))
    run_parse(str(source_id), trigger="reparse", from_where="reparse")

    runs = client.get(f"/api/workspaces/{workspace.id}/source-files/{source_id}/refresh-runs/")
    assert runs.status_code == status.HTTP_200_OK
    assert len(runs.data) >= 2

    snaps = client.get(f"/api/workspaces/{workspace.id}/source-files/{source_id}/snapshots/")
    assert snaps.status_code == status.HTTP_200_OK
    assert len(snaps.data) >= 2
    active = next(s for s in snaps.data if s["is_active"])
    assert "data" not in active

    detail = client.get(
        f"/api/workspaces/{workspace.id}/source-files/{source_id}/snapshots/{active['id']}/",
    )
    assert detail.status_code == status.HTTP_200_OK
    assert "rows" in detail.data["data"]["sheets"][0]

    compare = client.get(
        f"/api/workspaces/{workspace.id}/source-files/{source_id}/snapshots/compare/",
    )
    assert compare.status_code == status.HTTP_200_OK
    assert "summary" in compare.data

    source_detail = client.get(f"/api/workspaces/{workspace.id}/source-files/{source_id}/")
    assert source_detail.data["active_snapshot"]["id"] == active["id"]


def test_viewer_can_read_snapshots(editor_client):
    _client, owner = editor_client
    workspace = create_workspace_with_owner(user=owner)
    upload = make_uploaded_csv()
    created = _client.post(
        f"/api/workspaces/{workspace.id}/source-files/",
        {"file": upload},
        format="multipart",
    )
    source_id = created.data["id"]
    run_parse(str(source_id))

    viewer = ActiveUserFactory(email="viewer-snap@example.com")
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    viewer_client = APIClient()
    viewer_client.force_authenticate(user=viewer)
    response = viewer_client.get(
        f"/api/workspaces/{workspace.id}/source-files/{source_id}/snapshots/",
    )
    assert response.status_code == status.HTTP_200_OK


def test_other_workspace_snapshot_404(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    other = create_workspace_with_owner()
    upload = make_uploaded_csv()
    created = client.post(
        f"/api/workspaces/{workspace.id}/source-files/",
        {"file": upload},
        format="multipart",
    )
    source_id = created.data["id"]
    run_parse(str(source_id))
    snaps = client.get(f"/api/workspaces/{workspace.id}/source-files/{source_id}/snapshots/")
    snap_id = snaps.data[0]["id"]

    other_client = APIClient()
    other_user = other.owner
    other_client.force_authenticate(user=other_user)
    response = other_client.get(
        f"/api/workspaces/{other.id}/source-files/{source_id}/snapshots/{snap_id}/",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
