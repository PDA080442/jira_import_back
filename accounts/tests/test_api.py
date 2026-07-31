import re

import pytest
from django.core import mail
from rest_framework import status

from accounts.models import User
from accounts.services.email_verification import create_verification_token
from accounts.tests.factories import ActiveUserFactory, UserFactory
from audit.models import AuditLog


def _extract_token_from_email(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match, f"Token not found in email body: {body}"
    return match.group(1)


@pytest.mark.django_db
def test_register_verify_login_me_flow(api_client):
    register_response = api_client.post(
        "/api/auth/register/",
        {
            "email": "flow@example.com",
            "password": "password12345",
            "password_confirm": "password12345",
        },
        format="json",
    )
    assert register_response.status_code == status.HTTP_201_CREATED
    assert register_response.data["email"] == "flow@example.com"
    assert len(mail.outbox) == 1

    raw_token = _extract_token_from_email(mail.outbox[0].body)
    verify_response = api_client.post(
        "/api/auth/verify-email/",
        {"token": raw_token},
        format="json",
    )
    assert verify_response.status_code == status.HTTP_200_OK

    login_response = api_client.post(
        "/api/auth/login/",
        {"email": "flow@example.com", "password": "password12345"},
        format="json",
    )
    assert login_response.status_code == status.HTTP_200_OK
    access = login_response.data["access"]
    refresh = login_response.data["refresh"]

    me_response = api_client.get(
        "/api/me/",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert me_response.status_code == status.HTTP_200_OK
    assert me_response.data["email"] == "flow@example.com"
    assert me_response.data["locale"] == "ru-ru"

    patch_response = api_client.patch(
        "/api/me/",
        {"timezone": "Europe/Moscow", "locale": "en-us"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["timezone"] == "Europe/Moscow"

    logout_response = api_client.post(
        "/api/auth/logout/",
        {"refresh": refresh},
        format="json",
    )
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT

    refresh_response = api_client.post(
        "/api/auth/refresh/",
        {"refresh": refresh},
        format="json",
    )
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert refresh_response.data["code"] == "UNAUTHORIZED"


@pytest.mark.django_db
def test_register_duplicate_email_returns_validation_error(api_client):
    UserFactory(email="dup@example.com")

    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "dup@example.com",
            "password": "password12345",
            "password_confirm": "password12345",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "email" in response.data["fieldErrors"]


@pytest.mark.django_db
def test_login_unverified_returns_email_not_verified(api_client):
    user = UserFactory(email="unverified@example.com")
    user.set_password("password12345")
    user.save()

    response = api_client.post(
        "/api/auth/login/",
        {"email": "unverified@example.com", "password": "password12345"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "EMAIL_NOT_VERIFIED"


@pytest.mark.django_db
def test_login_wrong_password_returns_invalid_credentials(api_client):
    user = ActiveUserFactory(email="wrongpass@example.com")
    user.set_password("password12345")
    user.save()

    response = api_client.post(
        "/api/auth/login/",
        {"email": "wrongpass@example.com", "password": "bad-password"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["code"] == "INVALID_CREDENTIALS"


@pytest.mark.django_db
def test_patch_profile_invalid_timezone(api_client):
    user = ActiveUserFactory(email="tz@example.com")
    user.set_password("password12345")
    user.save()

    login_response = api_client.post(
        "/api/auth/login/",
        {"email": "tz@example.com", "password": "password12345"},
        format="json",
    )
    access = login_response.data["access"]

    response = api_client.patch(
        "/api/me/",
        {"timezone": "Not/A_Timezone"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "timezone" in response.data["fieldErrors"]


@pytest.mark.django_db
def test_password_reset_neutral_response(api_client):
    user = ActiveUserFactory(email="reset@example.com")

    response = api_client.post(
        "/api/auth/password/reset/",
        {"email": "reset@example.com"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    unknown_response = api_client.post(
        "/api/auth/password/reset/",
        {"email": "unknown@example.com"},
        format="json",
    )
    assert unknown_response.status_code == status.HTTP_200_OK
    assert unknown_response.data == response.data
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]


@pytest.mark.django_db
def test_password_confirm_flow(api_client):
    user = ActiveUserFactory(email="confirm@example.com")
    user.set_password("password12345")
    user.save()

    api_client.post(
        "/api/auth/password/reset/",
        {"email": "confirm@example.com"},
        format="json",
    )
    raw_token = _extract_token_from_email(mail.outbox[0].body)

    confirm_response = api_client.post(
        "/api/auth/password/confirm/",
        {
            "token": raw_token,
            "password": "newpassword99",
            "password_confirm": "newpassword99",
        },
        format="json",
    )
    assert confirm_response.status_code == status.HTTP_200_OK

    login_response = api_client.post(
        "/api/auth/login/",
        {"email": "confirm@example.com", "password": "newpassword99"},
        format="json",
    )
    assert login_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get("/api/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_register_audit_has_no_password(api_client):
    api_client.post(
        "/api/auth/register/",
        {
            "email": "audit@example.com",
            "password": "password12345",
            "password_confirm": "password12345",
        },
        format="json",
    )

    audit = AuditLog.objects.get(action="auth.register")
    assert "password" not in audit.payload_snapshot
    assert audit.payload_snapshot["email"] == "audit@example.com"


@pytest.mark.django_db
def test_verify_email_invalid_token(api_client):
    response = api_client.post(
        "/api/auth/verify-email/",
        {"token": "invalid-token-value"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "TOKEN_INVALID"
