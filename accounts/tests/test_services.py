import pytest
from django.core import mail

from accounts.models import EmailVerificationToken, Profile, User
from accounts.services import auth as auth_service
from accounts.services.email_verification import create_verification_token, verify_email
from accounts.tests.factories import UserFactory
from audit.models import AuditLog
from core.exceptions import ApiError


@pytest.mark.django_db
def test_register_user_creates_inactive_user_profile_and_token():
    user = auth_service.register_user(
        email="new@example.com",
        password="password12345",
    )

    assert user.is_active is False
    assert Profile.objects.filter(user=user).exists()
    assert EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).exists()
    assert AuditLog.objects.filter(action="auth.register").exists()
    assert len(mail.outbox) == 1
    assert "new@example.com" in mail.outbox[0].to


@pytest.mark.django_db
def test_verify_email_activates_user():
    user = UserFactory(email="verify@example.com")
    Profile.objects.create(user=user)
    _, raw_token = create_verification_token(user)

    activated = verify_email(raw_token)

    assert activated.is_active is True
    token = EmailVerificationToken.objects.get(user=user)
    assert token.used_at is not None


@pytest.mark.django_db
def test_verify_email_expired_token_raises():
    user = UserFactory()
    Profile.objects.create(user=user)
    _, raw_token = create_verification_token(user)
    token = EmailVerificationToken.objects.get(user=user)
    token.expires_at = token.expires_at.replace(year=2000)
    token.save(update_fields=["expires_at"])

    with pytest.raises(ApiError) as exc:
        verify_email(raw_token)

    assert exc.value.default_code == "TOKEN_EXPIRED"


@pytest.mark.django_db
def test_login_before_verify_raises_email_not_verified():
    user = UserFactory(email="inactive@example.com")
    user.set_password("password12345")
    user.save()

    with pytest.raises(ApiError) as exc:
        auth_service.login_user(email="inactive@example.com", password="password12345")

    assert exc.value.default_code == "EMAIL_NOT_VERIFIED"
    assert exc.value.status_code == 403


@pytest.mark.django_db
def test_login_invalid_credentials():
    user = UserFactory(email="active@example.com", is_active=True)
    user.set_password("password12345")
    user.save()

    with pytest.raises(ApiError) as exc:
        auth_service.login_user(email="active@example.com", password="wrong-password")

    assert exc.value.default_code == "INVALID_CREDENTIALS"
    assert exc.value.status_code == 401


@pytest.mark.django_db
def test_login_success_returns_tokens():
    user = UserFactory(email="active@example.com", is_active=True)
    user.set_password("password12345")
    user.save()

    tokens = auth_service.login_user(email="active@example.com", password="password12345")

    assert "access" in tokens
    assert "refresh" in tokens
    assert AuditLog.objects.filter(action="auth.login", actor=user).exists()
