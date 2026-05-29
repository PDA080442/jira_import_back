from unittest.mock import patch

import pytest

from audit.models import AuditLog
from core.context import TRACE_ID_HEADER


@pytest.mark.django_db
def test_health_live_returns_ok(api_client):
    response = api_client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert TRACE_ID_HEADER in response


@pytest.mark.django_db
def test_health_live_preserves_trace_id(api_client, trace_id):
    response = api_client.get("/health/", HTTP_X_TRACE_ID=trace_id)

    assert response[TRACE_ID_HEADER] == trace_id


@pytest.mark.django_db
def test_health_ready_returns_503_on_failure(api_client):
    checks = {
        "database": {"status": "ok", "detail": "ok"},
        "redis": {"status": "error", "detail": "redis down"},
        "celery_broker": {"status": "ok", "detail": "ok"},
        "celery_workers": {"status": "ok", "detail": "ok"},
    }
    with patch("core.views.run_readiness_checks", return_value=checks):
        response = api_client.get("/ready/")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert AuditLog.objects.filter(action="readiness.check.failed").exists()


@pytest.mark.django_db
def test_health_ready_returns_200_when_ready(api_client):
    checks = {
        "database": {"status": "ok", "detail": "ok"},
        "redis": {"status": "ok", "detail": "ok"},
        "celery_broker": {"status": "ok", "detail": "ok"},
        "celery_workers": {"status": "ok", "detail": "ok"},
    }
    with patch("core.views.run_readiness_checks", return_value=checks):
        response = api_client.get("/ready/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
