import pytest
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from jira.models import JiraGuide

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def guide():
    obj, _ = JiraGuide.objects.update_or_create(
        slug="jira-connection-setup",
        defaults={
            "title": "Подключение Jira Cloud: пошаговая инструкция",
            "summary": "Короткое описание",
            "locale": "ru",
            "content": [
                {"id": "intro", "title": "Что это", "blocks": [{"type": "paragraph", "text": "..."}]}
            ],
            "version": 1,
            "is_published": True,
        },
    )
    return obj


def test_get_guide_returns_content(auth_client, guide):
    resp = auth_client.get(f"/api/jira/guides/{guide.slug}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "jira-connection-setup"
    assert data["locale"] == "ru"
    assert isinstance(data["content"], list)
    assert data["content"][0]["id"] == "intro"


def test_get_guide_unknown_slug_returns_404(auth_client):
    resp = auth_client.get("/api/jira/guides/does-not-exist/")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_get_unpublished_guide_returns_404(auth_client):
    JiraGuide.objects.create(slug="draft", title="Draft", is_published=False)
    resp = auth_client.get("/api/jira/guides/draft/")
    assert resp.status_code == 404


def test_list_guides_excludes_unpublished(auth_client, guide):
    JiraGuide.objects.create(slug="draft", title="Draft", is_published=False)
    resp = auth_client.get("/api/jira/guides/")
    assert resp.status_code == 200
    slugs = [g["slug"] for g in resp.json()]
    assert "jira-connection-setup" in slugs
    assert "draft" not in slugs


def test_guide_requires_auth(guide):
    resp = APIClient().get(f"/api/jira/guides/{guide.slug}/")
    assert resp.status_code == 401
