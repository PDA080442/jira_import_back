"""Email verification token lifecycle and user activation."""
from django.utils import timezone

from accounts.models import EmailVerificationToken, User
from accounts.services.tokens import (
    generate_raw_token,
    hash_token,
    is_token_expired,
    verification_expires_at,
)
from core.exceptions import ApiError


def invalidate_pending_tokens(user: User) -> None:
    # Only one active verify link per user at a time.
    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now(),
    )


def create_verification_token(user: User) -> tuple[EmailVerificationToken, str]:
    """Return (db_token, raw_token); raw is passed to Celery only, never persisted."""
    invalidate_pending_tokens(user)
    raw_token = generate_raw_token()
    token = EmailVerificationToken.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        expires_at=verification_expires_at(),
    )
    return token, raw_token


def verify_email(raw_token: str) -> User:
    token_hash = hash_token(raw_token)
    try:
        token = EmailVerificationToken.objects.select_related("user").get(
            token_hash=token_hash,
        )
    except EmailVerificationToken.DoesNotExist as exc:
        raise ApiError(
            detail="Invalid verification token.",
            code="TOKEN_INVALID",
            status_code=400,
        ) from exc

    if token.used_at is not None:
        raise ApiError(
            detail="Invalid verification token.",
            code="TOKEN_INVALID",
            status_code=400,
        )

    if is_token_expired(token.expires_at):
        raise ApiError(
            detail="Verification token has expired.",
            code="TOKEN_EXPIRED",
            status_code=400,
        )

    user = token.user
    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])

    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])

    return user
