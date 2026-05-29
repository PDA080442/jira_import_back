import pytest

from audit.models import AuditLog
from audit.services.log_action import log_action
from core.logging import redact_mapping


@pytest.mark.django_db
def test_log_action_persists_audit_log():
    audit = log_action(
        action="test.action",
        entity_type="system",
        entity_id="1",
        trace_id="audit-trace",
        payload={"message": "hello"},
    )

    assert AuditLog.objects.count() == 1
    assert audit.trace_id == "audit-trace"
    assert audit.payload_snapshot["message"] == "hello"


def test_redact_mapping_masks_secrets():
    payload = redact_mapping(
        {
            "password": "secret",
            "token": "abc",
            "DATABASE_URL": "postgres://user:pass@localhost/db",
            "safe": "value",
        }
    )

    assert payload["password"] == "***REDACTED***"
    assert payload["token"] == "***REDACTED***"
    assert "pass" not in payload["DATABASE_URL"]
    assert payload["safe"] == "value"
