import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from jira.models import JiraSyncStatus
from jira.services.jira_client import (
    JiraBoardResult,
    JiraMetadataFetchResult,
    JiraProjectResult,
    JiraSprintResult,
)
from jira.tests.factories import create_jira_connection, create_jira_metadata, populate_sample_metadata
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner


@pytest.fixture
def owner_client():
    user = ActiveUserFactory(email="owner-meta@example.com")
    user.set_password("password12345")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def viewer_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client, other_user


@pytest.fixture
def other_user():
    user = ActiveUserFactory(email="viewer-meta@example.com")
    user.set_password("password12345")
    user.save()
    return user


def _metadata_url(workspace_id, connection_id):
    return f"/api/workspaces/{workspace_id}/jira-connections/{connection_id}/metadata/"


def _sync_url(workspace_id, connection_id):
    return f"/api/workspaces/{workspace_id}/jira-connections/{connection_id}/sync-metadata/"


def _sample_fetch_result():
    return JiraMetadataFetchResult(
        project=JiraProjectResult(
            project_id="10001",
            project_key="PROJ",
            project_name="Demo Project",
            issue_types=[{"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0}],
        ),
        issue_types=[{"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0}],
        fields=[
            {
                "id": "summary",
                "key": "summary",
                "name": "Summary",
                "custom": False,
                "schema": {"type": "string"},
            },
        ],
        required_field_keys={"summary"},
        priorities=[{"id": "1", "name": "High"}],
        statuses=[{"id": "3", "name": "In Progress", "statusCategory": {"name": "In Progress"}}],
        components=[{"id": "10000", "name": "Backend"}],
        labels=["bug"],
        boards=[JiraBoardResult(board_id="42", name="Scrum board", board_type="scrum")],
        sprints_by_board={
            "42": [
                JiraSprintResult(
                    sprint_id="101",
                    name="Sprint 1",
                    state="active",
                    start_date=None,
                    end_date=None,
                    goal="MVP",
                ),
            ],
        },
    )


@pytest.mark.django_db
def test_get_metadata_pending(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)

    response = client.get(_metadata_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == JiraSyncStatus.PENDING
    assert response.data["is_stale"] is True
    assert response.data["issue_types"] == []


@pytest.mark.django_db
def test_get_metadata_fresh(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)
    metadata = create_jira_metadata(
        connection=connection,
        status=JiraSyncStatus.FRESH,
        fetched_at=timezone.now(),
    )
    populate_sample_metadata(metadata)

    response = client.get(_metadata_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == JiraSyncStatus.FRESH
    assert response.data["is_stale"] is False
    assert len(response.data["issue_types"]) == 1
    assert response.data["fields"][0]["template_field_type"] == "text"
    assert len(response.data["boards"]) == 1
    assert len(response.data["boards"][0]["sprints"]) == 1


@pytest.mark.django_db
def test_get_metadata_stale(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)
    create_jira_metadata(
        connection=connection,
        status=JiraSyncStatus.FRESH,
        fetched_at=timezone.now() - timezone.timedelta(hours=2),
        ttl_seconds=3600,
    )

    response = client.get(_metadata_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_stale"] is True


@pytest.mark.django_db
def test_get_metadata_non_member_returns_404(owner_client, other_user):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)

    outsider = APIClient()
    outsider.force_authenticate(user=other_user)
    response = outsider.get(_metadata_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_sync_metadata_forbidden_for_viewer(owner_client, viewer_client):
    owner_api, owner = owner_client
    viewer_api, viewer = viewer_client
    workspace = create_workspace_with_owner(user=owner)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer,
        role=WorkspaceRole.VIEWER,
    )
    connection = create_jira_connection(workspace=workspace, user=owner)

    response = viewer_api.post(_sync_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_sync_metadata_accepted(owner_client, monkeypatch):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)

    monkeypatch.setattr(
        "jira.services.metadata.fetch_project_metadata",
        lambda **kwargs: _sample_fetch_result(),
    )

    def _run_sync(connection_id):
        from jira.services.metadata import run_metadata_sync

        run_metadata_sync(connection_id)

    monkeypatch.setattr("jira.tasks.sync_jira_metadata.delay", _run_sync)

    response = client.post(_sync_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["status"] == JiraSyncStatus.SYNCING

    metadata_response = client.get(_metadata_url(workspace.id, connection.id))
    assert metadata_response.status_code == status.HTTP_200_OK
    assert metadata_response.data["status"] == JiraSyncStatus.FRESH
    assert len(metadata_response.data["fields"]) == 1


@pytest.mark.django_db
def test_sync_metadata_in_progress_conflict(owner_client, monkeypatch):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)
    create_jira_metadata(connection=connection, status=JiraSyncStatus.SYNCING)

    response = client.post(_sync_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "SYNC_IN_PROGRESS"


@pytest.mark.django_db
def test_sync_metadata_deactivated_connection(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user, is_active=False)

    response = client.post(_sync_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"
