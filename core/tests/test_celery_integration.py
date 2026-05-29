import pytest

from core.tasks import ping


@pytest.mark.django_db
def test_ping_task_returns_pong():
    result = ping.apply(args=[], kwargs={"trace_id": "celery-trace"}).get()

    assert result == "pong"


@pytest.mark.django_db
def test_ping_task_writes_audit_log():
    from audit.models import AuditLog

    ping.apply(args=[], kwargs={"trace_id": "celery-trace"}).get()

    audit = AuditLog.objects.get(action="celery.ping.succeeded")
    assert audit.trace_id == "celery-trace"
    assert audit.entity_type == "celery_task"
