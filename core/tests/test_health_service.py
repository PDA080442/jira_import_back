from unittest.mock import MagicMock, patch

import pytest

from core.services import health


@pytest.mark.parametrize(
    ("checker_name", "failed_checker"),
    [
        ("check_database", "database"),
        ("check_redis", "redis"),
        ("check_celery_broker", "celery_broker"),
        ("check_celery_workers", "celery_workers"),
    ],
)
def test_run_readiness_checks_partial_failure(checker_name, failed_checker):
    with (
        patch.object(health, "check_database", return_value=(True, "ok")),
        patch.object(health, "check_redis", return_value=(True, "ok")),
        patch.object(health, "check_celery_broker", return_value=(True, "ok")),
        patch.object(health, "check_celery_workers", return_value=(True, "ok")),
    ):
        setattr(health, checker_name, MagicMock(return_value=(False, "boom")))
        checks = health.run_readiness_checks()

    assert checks[failed_checker]["status"] == "error"
    assert checks[failed_checker]["detail"] == "boom"
    assert health.is_ready(checks) is False


def test_run_readiness_checks_all_ok():
    with (
        patch.object(health, "check_database", return_value=(True, "ok")),
        patch.object(health, "check_redis", return_value=(True, "ok")),
        patch.object(health, "check_celery_broker", return_value=(True, "ok")),
        patch.object(health, "check_celery_workers", return_value=(True, "ok")),
    ):
        checks = health.run_readiness_checks()

    assert health.is_ready(checks) is True


def test_check_database_failure():
    with patch.object(health.connection, "ensure_connection", side_effect=Exception("db down")):
        ok, detail = health.check_database()

    assert ok is False
    assert "db down" in detail
