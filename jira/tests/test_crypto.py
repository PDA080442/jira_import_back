import pytest

from jira.services.crypto import decrypt_secret, encrypt_secret
from jira.tests.factories import create_jira_connection


@pytest.mark.django_db
def test_encrypt_decrypt_roundtrip():
    plaintext = "my-secret-jira-token"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext


@pytest.mark.django_db
def test_encrypted_token_not_plaintext_in_db():
    connection = create_jira_connection(api_token="super-secret-token")
    connection.refresh_from_db()
    assert "super-secret-token" not in connection.api_token_encrypted
    assert decrypt_secret(connection.api_token_encrypted) == "super-secret-token"
