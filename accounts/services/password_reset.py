"""Password reset token lifecycle."""
from django.utils import timezone

from accounts.models import PasswordResetToken, User
from accounts.services.tokens import (
    generate_raw_token,
    hash_token,
    is_token_expired,
    password_reset_expires_at,
)
from core.exceptions import ApiError


def invalidate_pending_reset_tokens(user: User) -> None:
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now(),
    )


def create_password_reset_token(user: User) -> tuple[PasswordResetToken, str]:
    invalidate_pending_reset_tokens(user)
    raw_token = generate_raw_token()
    token = PasswordResetToken.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        expires_at=password_reset_expires_at(),
    )
    return token, raw_token


def confirm_password_reset(raw_token: str, password: str) -> User:
    token_hash = hash_token(raw_token)
    try:
        token = PasswordResetToken.objects.select_related("user").get(
            token_hash=token_hash,
        )
    except PasswordResetToken.DoesNotExist as exc:
        raise ApiError(
            detail="Invalid reset token.",
            code="TOKEN_INVALID",
            status_code=400,
        ) from exc

    if token.used_at is not None:
        raise ApiError(
            detail="Invalid reset token.",
            code="TOKEN_INVALID",
            status_code=400,
        )

    if is_token_expired(token.expires_at):
        raise ApiError(
            detail="Reset token has expired.",
            code="TOKEN_EXPIRED",
            status_code=400,
        )

    user = token.user
    user.set_password(password)
    user.save(update_fields=["password", "updated_at"])

    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])

    return user
