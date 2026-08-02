from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ENDPOINT = "/api/jira/guides/"


def test_expired_token_returns_token_expired():
    user = UserFactory()
    token = AccessToken.for_user(user)
    token.set_exp(from_time=timezone.now() - timedelta(days=10), lifetime=timedelta(days=1))

    resp = APIClient().get(ENDPOINT, HTTP_AUTHORIZATION=f"Bearer {token}")

    assert resp.status_code == 401
    assert resp.json()["code"] == "TOKEN_EXPIRED"


def test_malformed_token_returns_token_not_valid():
    resp = APIClient().get(ENDPOINT, HTTP_AUTHORIZATION="Bearer not-a-real-token")

    assert resp.status_code == 401
    assert resp.json()["code"] == "TOKEN_NOT_VALID"


def test_missing_token_returns_unauthorized():
    resp = APIClient().get(ENDPOINT)

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"
