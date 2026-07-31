import re

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tests.factories import ActiveUserFactory
from tenants.models import WorkspaceMembership, WorkspaceRole
from tenants.services.invite import create_invite
from tenants.tests.factories import create_workspace_with_owner


@pytest.fixture
def auth_client():
    user = ActiveUserFactory(email="owner@example.com")
    user.set_password("password12345")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def other_user():
    user = ActiveUserFactory(email="editor@example.com")
    user.set_password("password12345")
    user.save()
    return user


def _extract_token(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match
    return match.group(1)


@pytest.mark.django_db
def test_create_and_list_workspace(auth_client):
    client, user = auth_client

    create_response = client.post(
        "/api/workspaces/",
        {"name": "My Team"},
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["name"] == "My Team"
    assert create_response.data["owner_id"] == str(user.id)

    list_response = client.get("/api/workspaces/")
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.data) == 1


@pytest.mark.django_db
def test_get_workspace_members(auth_client):
    client, user = auth_client
    workspace = create_workspace_with_owner(user=user, name="Members WS")

    response = client.get(f"/api/workspaces/{workspace.id}/members/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["members"]) == 1
    assert response.data["members"][0]["email"] == user.email
    assert response.data["members"][0]["role"] == WorkspaceRole.OWNER


@pytest.mark.django_db
def test_non_member_get_workspace_returns_404(auth_client, other_user):
    client, _ = auth_client
    workspace = create_workspace_with_owner(user=other_user, name="Private")

    response = client.get(f"/api/workspaces/{workspace.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_viewer_cannot_patch_workspace(auth_client, other_user):
    client, owner = auth_client
    workspace = create_workspace_with_owner(user=owner, name="Patch WS")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=other_user,
        role=WorkspaceRole.VIEWER,
    )
    viewer_client = APIClient()
    viewer_client.force_authenticate(user=other_user)

    response = viewer_client.patch(
        f"/api/workspaces/{workspace.id}/",
        {"name": "Hacked"},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_owner_can_delete_workspace(auth_client):
    client, user = auth_client
    workspace = create_workspace_with_owner(user=user, name="Delete Me")

    response = client.delete(f"/api/workspaces/{workspace.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_invite_and_accept_flow(auth_client):
    client, admin_user = auth_client
    workspace = create_workspace_with_owner(user=admin_user, name="Invite WS")
    invitee = ActiveUserFactory(email="invitee@example.com")
    invitee.set_password("password12345")
    invitee.save()

    invite_response = client.post(
        f"/api/workspaces/{workspace.id}/invites/",
        {"email": "invitee@example.com", "role": WorkspaceRole.EDITOR},
        format="json",
    )
    assert invite_response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    raw_token = _extract_token(mail.outbox[0].body)
    invitee_client = APIClient()
    invitee_client.force_authenticate(user=invitee)

    accept_response = invitee_client.post(
        "/api/workspaces/invites/accept/",
        {"token": raw_token},
        format="json",
    )
    assert accept_response.status_code == status.HTTP_200_OK
    assert accept_response.data["role"] == WorkspaceRole.EDITOR
    assert WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=invitee,
        role=WorkspaceRole.EDITOR,
    ).exists()


@pytest.mark.django_db
def test_accept_invite_wrong_email_forbidden(auth_client):
    client, admin_user = auth_client
    workspace = create_workspace_with_owner(user=admin_user, name="Wrong Email WS")

    client.post(
        f"/api/workspaces/{workspace.id}/invites/",
        {"email": "invitee@example.com", "role": WorkspaceRole.VIEWER},
        format="json",
    )
    raw_token = _extract_token(mail.outbox[0].body)

    other = ActiveUserFactory(email="other@example.com")
    other_client = APIClient()
    other_client.force_authenticate(user=other)

    response = other_client.post(
        "/api/workspaces/invites/accept/",
        {"token": raw_token},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
