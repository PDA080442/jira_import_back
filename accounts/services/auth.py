"""Auth orchestration: register, login, logout, password reset; audit + Celery."""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Profile, User
from accounts.services.email_verification import create_verification_token, verify_email
from accounts.services.password_reset import (
    confirm_password_reset,
    create_password_reset_token,
)
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger

logger = get_logger("accounts.auth")


def register_user(*, email: str, password: str) -> User:
    """Create inactive user, profile, verification token; enqueue email task."""
    from accounts.tasks import send_verification_email

    email = User.objects.normalize_email(email)
    user = User.objects.create_user(email=email, password=password)
    Profile.objects.create(user=user)

    token, raw_token = create_verification_token(user)
    send_verification_email.delay(str(token.id), raw_token)

    log_action(
        action="auth.register",
        entity_type="user",
        entity_id=str(user.id),
        payload={"email": email},
    )
    logger.info("auth_register_succeeded", user_id=str(user.id))
    return user


def verify_user_email(*, raw_token: str) -> User:
    user = verify_email(raw_token)
    log_action(
        action="auth.verify_email",
        entity_type="user",
        entity_id=str(user.id),
        actor=user,
        payload={"user_id": str(user.id)},
    )
    logger.info("auth_verify_succeeded", user_id=str(user.id))
    return user


def login_user(*, email: str, password: str) -> dict[str, str]:
    """Issue JWT pair; inactive users with valid password get EMAIL_NOT_VERIFIED."""
    email = User.objects.normalize_email(email)
    existing_user = User.objects.filter(email=email).first()

    # authenticate() returns None for inactive users — handle explicitly for UX code.
    if existing_user is not None and not existing_user.is_active:
        if existing_user.check_password(password):
            raise ApiError(
                detail="Email is not verified.",
                code="EMAIL_NOT_VERIFIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        logger.info("auth_login_failed", email=email)
        raise ApiError(
            detail="Invalid credentials.",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = authenticate(username=email, password=password)

    if user is None:
        logger.info("auth_login_failed", email=email)
        raise ApiError(
            detail="Invalid credentials.",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)
    log_action(
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        actor=user,
        payload={"user_id": str(user.id)},
    )
    logger.info("auth_login_succeeded", user_id=str(user.id))
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def logout_user(*, refresh_token: str, user: User | None = None) -> None:
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception as exc:
        raise ApiError(
            detail="Invalid refresh token.",
            code="TOKEN_INVALID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    actor = user
    if actor is None:
        user_id = token.get("user_id")
        if user_id:
            actor = User.objects.filter(id=user_id).first()

    log_action(
        action="auth.logout",
        entity_type="user",
        entity_id=str(actor.id) if actor else "",
        actor=actor,
        payload={"user_id": str(actor.id) if actor else ""},
    )
    logger.info("auth_logout", user_id=str(actor.id) if actor else "")


def request_password_reset(*, email: str) -> None:
    """Always silent when email unknown — no user enumeration."""
    from accounts.tasks import send_password_reset_email

    email = User.objects.normalize_email(email)
    user = User.objects.filter(email=email).first()
    if user is None:
        return

    token, raw_token = create_password_reset_token(user)
    send_password_reset_email.delay(str(token.id), raw_token)

    log_action(
        action="auth.password_reset_requested",
        entity_type="user",
        entity_id=str(user.id),
        payload={},
    )


def reset_password(*, raw_token: str, password: str) -> User:
    user = confirm_password_reset(raw_token, password)
    log_action(
        action="auth.password_reset_confirmed",
        entity_type="user",
        entity_id=str(user.id),
        actor=user,
        payload={"user_id": str(user.id)},
    )
    return user
