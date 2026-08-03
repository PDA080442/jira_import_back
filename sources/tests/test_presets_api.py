"""API tests for source presets."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from sources.models import PresetSourceType, SourceParseStatus
from sources.services.parsing import run_parse
from sources.tests.factories import (
    SourceSheetFactory,
    create_source_file,
    create_source_preset,
    make_uploaded_csv,
)
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor_client():
    user = ActiveUserFactory(email="editor-presets@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def viewer_client():
    user = ActiveUserFactory(email="viewer-presets@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _presets_url(workspace_id):
    return f"/api/workspaces/{workspace_id}/source-presets/"


def _preset_detail_url(workspace_id, preset_id):
    return f"/api/workspaces/{workspace_id}/source-presets/{preset_id}/"


def _apply_file_url(workspace_id, source_id):
    return f"/api/workspaces/{workspace_id}/source-files/{source_id}/apply-preset/"


def test_create_and_list_presets(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    payload = {
        "name": "Semicolon CSV",
        "source_type": "file",
        "settings": {"delimiter": "semicolon", "encoding": "utf-8"},
    }
    response = client.post(_presets_url(workspace.id), payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["version"] == 1

    listing = client.get(_presets_url(workspace.id))
    assert listing.status_code == status.HTTP_200_OK
    assert len(listing.data) == 1


def test_viewer_cannot_create_preset(viewer_client):
    client, user = viewer_client
    workspace = create_workspace_with_owner()
    WorkspaceMembership.objects.create(user=user, workspace=workspace, role=WorkspaceRole.VIEWER)
    response = client.post(
        _presets_url(workspace.id),
        {"name": "X", "source_type": "file", "settings": {}},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_duplicate_preset_name_rejected(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    payload = {"name": "Same", "source_type": "file", "settings": {}}
    assert client.post(_presets_url(workspace.id), payload, format="json").status_code == 201
    dup = client.post(_presets_url(workspace.id), payload, format="json")
    assert dup.status_code == status.HTTP_400_BAD_REQUEST


def test_apply_preset_to_file(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_a, **_k: None)

    preset = create_source_preset(
        workspace=workspace,
        user=user,
        settings={"delimiter": "semicolon"},
    )
    source = create_source_file(workspace=workspace, user=user, status=SourceParseStatus.READY)
    SourceSheetFactory(source_file=source, name="Sheet1")

    response = client.post(
        _apply_file_url(workspace.id, source.id),
        {"preset_id": str(preset.id)},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "applied"

    source.refresh_from_db()
    assert source.delimiter_override == ";"


def test_upload_with_preset_id(editor_client, monkeypatch):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_a, **_k: None)

    preset = create_source_preset(
        workspace=workspace,
        user=user,
        settings={"delimiter": "semicolon", "encoding": "utf-8"},
    )
    upload = make_uploaded_csv(content="A;B\n1;2\n")
    response = client.post(
        f"/api/workspaces/{workspace.id}/source-files/",
        {"file": upload, "preset_id": str(preset.id)},
        format="multipart",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["applied_preset"]["id"] == str(preset.id)


def test_update_preset_marks_binding_stale(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    preset = create_source_preset(workspace=workspace, user=user, settings={"delimiter": "comma"})
    source = create_source_file(workspace=workspace, user=user)
    from sources.services import presets as presets_service

    presets_service.create_initial_binding(
        preset=preset,
        user=user,
        source_type=PresetSourceType.FILE,
        source_id=source.id,
        settings=preset.settings,
    )

    patch = client.patch(
        _preset_detail_url(workspace.id, preset.id),
        {"settings": {"delimiter": "semicolon"}},
        format="json",
    )
    assert patch.status_code == status.HTTP_200_OK
    assert patch.data["version"] == 2

    recent = client.get(f"/api/workspaces/{workspace.id}/source-presets/recent/")
    assert recent.status_code == status.HTTP_200_OK
    assert recent.data[0]["is_stale"] is True


def test_google_preset_rejects_file_only_settings(editor_client):
    client, user = editor_client
    workspace = create_workspace_with_owner(user=user)
    response = client.post(
        _presets_url(workspace.id),
        {
            "name": "Bad Google",
            "source_type": "google",
            "settings": {"delimiter": "comma"},
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
