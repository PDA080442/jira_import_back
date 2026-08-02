"""Fernet encryption for secrets at rest."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from core.exceptions import ApiError
from rest_framework import status


def _get_fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        raise ApiError(
            detail="API token is required.",
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        plaintext = _get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise ApiError(
            detail="Stored credentials are invalid.",
            code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc
    return plaintext.decode("utf-8")
