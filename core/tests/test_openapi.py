"""OpenAPI schema generation smoke tests."""
import json

import pytest
from django.urls import reverse


def _fetch_openapi_schema(api_client):
    response = api_client.get(
        reverse("schema"),
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    return json.loads(response.content)


@pytest.mark.django_db
def test_openapi_schema_endpoint_returns_200(api_client):
    response = api_client.get(
        reverse("schema"),
        HTTP_ACCEPT="application/vnd.oai.openapi+json",
    )
    assert response.status_code == 200
    assert "openapi" in response["Content-Type"]


def test_openapi_schema_contains_workspace_paths(api_client):
    schema = _fetch_openapi_schema(api_client)
    paths = schema.get("paths", {})
    assert "/api/workspaces/" in paths
    assert "/api/workspaces/{id}/" in paths
    assert "/api/workspaces/{id}/members/" in paths
    assert "/api/workspaces/{id}/invites/" in paths
    assert "/api/workspaces/invites/accept/" in paths


def test_openapi_schema_contains_auth_paths(api_client):
    schema = _fetch_openapi_schema(api_client)
    paths = schema.get("paths", {})
    assert "/api/auth/login/" in paths
    assert "/api/me/" in paths


def test_openapi_schema_contains_jira_paths(api_client):
    schema = _fetch_openapi_schema(api_client)
    paths = schema.get("paths", {})
    assert "/api/workspaces/{workspace_id}/jira-connections/" in paths
    assert "/api/workspaces/{workspace_id}/jira-connections/{id}/" in paths
    assert "/api/workspaces/{workspace_id}/jira-connections/{id}/test/" in paths
    assert "/api/workspaces/{workspace_id}/jira-connections/{id}/metadata/" in paths
    assert "/api/workspaces/{workspace_id}/jira-connections/{id}/sync-metadata/" in paths
