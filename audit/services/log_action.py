from core.logging import redact_mapping


def log_action(
    *,
    action: str,
    entity_type: str,
    entity_id: str = "",
    trace_id: str | None = None,
    actor=None,
    payload: dict | None = None,
) -> "AuditLog":
    from audit.models import AuditLog
    from core.context import get_trace_id
    from core.logging import get_logger

    logger = get_logger("audit")
    resolved_trace_id = trace_id or get_trace_id() or ""
    redacted_payload = redact_mapping(payload or {})

    audit_log = AuditLog.objects.create(
        trace_id=resolved_trace_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_snapshot=redacted_payload,
    )

    logger.info(
        "audit_action",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        audit_log_id=str(audit_log.id),
    )
    return audit_log
