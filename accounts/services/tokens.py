"""Token generation and hashing helpers shared by verify/reset flows."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verification_expires_at():
    return timezone.now() + timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS)


def password_reset_expires_at():
    return timezone.now() + timedelta(hours=settings.PASSWORD_RESET_TTL_HOURS)


def is_token_expired(expires_at) -> bool:
    return timezone.now() >= expires_at
