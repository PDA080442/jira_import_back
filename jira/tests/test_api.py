import json

import httpx
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import ActiveUserFactory
from jira.models import JiraTestStatus
from jira.services.jira_client import JiraAuthError, JiraClientError, verify_credentials
from jira.tests.factories import create_jira_connection
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.tests.factories import create_workspace_with_owner


@pytest.fixture
def owner_client():
    user = ActiveUserFactory(email="owner@example.com")
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
    user = ActiveUserFactory(email="viewer@example.com")
    user.set_password("password12345")
    user.save()
    return user


CONNECTION_PAYLOAD = {
    "name": "Prod Jira",
    "base_url": "https://example.atlassian.net",
    "email": "admin@example.com",
    "api_token": "secret-token-value",
    "project_key": "PROJ",
    "board_id": "99",
    "extra": {"note": "demo"},
}


def _connections_url(workspace_id):
    return f"/api/workspaces/{workspace_id}/jira-connections/"


def _connection_url(workspace_id, connection_id):
    return f"/api/workspaces/{workspace_id}/jira-connections/{connection_id}/"


@pytest.mark.django_db
def test_create_list_get_connection(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)

    create_response = client.post(
        _connections_url(workspace.id),
        CONNECTION_PAYLOAD,
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["name"] == "Prod Jira"
    assert create_response.data["has_api_token"] is True
    assert "api_token" not in create_response.data
    assert "api_token_encrypted" not in create_response.data

    list_response = client.get(_connections_url(workspace.id))
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.data) == 1

    connection_id = create_response.data["id"]
    get_response = client.get(_connection_url(workspace.id, connection_id))
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.data["project_key"] == "PROJ"


@pytest.mark.django_db
def test_non_member_get_connection_returns_404(owner_client, other_user):
    client, _ = owner_client
    workspace = create_workspace_with_owner(user=other_user)

    connection = create_jira_connection(workspace=workspace, user=other_user)
    response = client.get(_connection_url(workspace.id, connection.id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_viewer_cannot_create_connection(owner_client, viewer_client):
    _, owner = owner_client
    client, viewer = viewer_client
    workspace = create_workspace_with_owner(user=owner)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer,
        role=WorkspaceRole.VIEWER,
    )

    response = client.post(
        _connections_url(workspace.id),
        CONNECTION_PAYLOAD,
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_update_and_deactivate_connection(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user, name="Old Name")

    patch_response = client.patch(
        _connection_url(workspace.id, connection.id),
        {"name": "New Name", "is_active": False},
        format="json",
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["name"] == "New Name"
    assert patch_response.data["is_active"] is False

    deactivate_response = client.post(
        f"{_connection_url(workspace.id, connection.id)}deactivate/",
    )
    assert deactivate_response.status_code == status.HTTP_200_OK
    assert deactivate_response.data["is_active"] is False


@pytest.mark.django_db
def test_duplicate_name_validation_error(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    create_jira_connection(workspace=workspace, user=user, name="Duplicate")

    response = client.post(
        _connections_url(workspace.id),
        {**CONNECTION_PAYLOAD, "name": "Duplicate"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_connection_test_success(monkeypatch, owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)

    from jira.services import test as test_service

    def fake_verify(**kwargs):
        from jira.services.jira_client import JiraMyselfResult

        return JiraMyselfResult(
            account_id="acc-1",
            display_name="Admin",
            email_address="admin@example.com",
        )

    monkeypatch.setattr(test_service, "verify_credentials", fake_verify)

    response = client.post(
        f"{_connection_url(workspace.id, connection.id)}test/",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == JiraTestStatus.SUCCESS
    assert response.data["account"]["account_id"] == "acc-1"

    connection.refresh_from_db()
    assert connection.last_test_status == JiraTestStatus.SUCCESS


@pytest.mark.django_db
def test_connection_test_auth_failure(monkeypatch, owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)
    connection = create_jira_connection(workspace=workspace, user=user)

    from jira.services import test as test_service

    def fake_verify(**kwargs):
        raise JiraAuthError("Invalid credentials", 401)

    monkeypatch.setattr(test_service, "verify_credentials", fake_verify)

    response = client.post(
        f"{_connection_url(workspace.id, connection.id)}test/",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == JiraTestStatus.FAILED

    connection.refresh_from_db()
    assert connection.last_test_status == JiraTestStatus.FAILED


@pytest.mark.django_db
def test_invalid_base_url_rejected(owner_client):
    client, user = owner_client
    workspace = create_workspace_with_owner(user=user)

    response = client.post(
        _connections_url(workspace.id),
        {**CONNECTION_PAYLOAD, "base_url": "http://insecure.example.net"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_jira_client_verify_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/myself"
        return httpx.Response(
            200,
            json={
                "accountId": "acc-123",
                "displayName": "Test User",
                "emailAddress": "test@example.com",
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class PatchedClient(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = PatchedClient
    try:
        result = verify_credentials(
            base_url="https://example.atlassian.net",
            email="test@example.com",
            api_token="token",
        )
    finally:
        httpx.Client = original_client

    assert result.account_id == "acc-123"
    assert result.display_name == "Test User"


def test_jira_client_auth_error_no_retry():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class PatchedClient(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = PatchedClient
    try:
        with pytest.raises(JiraAuthError):
            verify_credentials(
                base_url="https://example.atlassian.net",
                email="bad@example.com",
                api_token="bad",
            )
    finally:
        httpx.Client = original_client

    assert calls["count"] == 1


def test_jira_client_retries_server_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(503, json={"error": "Unavailable"})
        return httpx.Response(
            200,
            json={"accountId": "a", "displayName": "n", "emailAddress": "e@x.com"},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class PatchedClient(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = PatchedClient
    try:
        result = verify_credentials(
            base_url="https://example.atlassian.net",
            email="test@example.com",
            api_token="token",
        )
    finally:
        httpx.Client = original_client

    assert calls["count"] == 2
    assert result.account_id == "a"
