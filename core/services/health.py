from django.conf import settings
from django.core.cache import cache
from django.db import connection


def check_database() -> tuple[bool, str]:
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_redis() -> tuple[bool, str]:
    try:
        key = "healthcheck:probe"
        cache.set(key, "ok", timeout=10)
        if cache.get(key) != "ok":
            return False, "cache read/write failed"
        cache.delete(key)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_celery_broker() -> tuple[bool, str]:
    try:
        from config.celery import app

        with app.connection_or_acquire() as conn:
            conn.ensure_connection(max_retries=1)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_celery_workers() -> tuple[bool, str]:
    try:
        from config.celery import app

        inspect = app.control.inspect(timeout=settings.HEALTHCHECK_CELERY_TIMEOUT)
        ping_response = inspect.ping()
        if not ping_response:
            return False, "no workers responded"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def run_readiness_checks() -> dict[str, dict[str, str]]:
    checks = {
        "database": _format_check(*check_database()),
        "redis": _format_check(*check_redis()),
        "celery_broker": _format_check(*check_celery_broker()),
        "celery_workers": _format_check(*check_celery_workers()),
    }
    return checks


def is_ready(checks: dict[str, dict[str, str]]) -> bool:
    return all(item["status"] == "ok" for item in checks.values())


def _format_check(ok: bool, detail: str) -> dict[str, str]:
    return {"status": "ok" if ok else "error", "detail": detail}
