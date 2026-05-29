from celery import shared_task

from audit.services.log_action import log_action
from core.context import get_trace_id
from core.logging import get_logger

logger = get_logger(__name__)


@shared_task(name="core.ping")
def ping(trace_id: str | None = None) -> str:
    resolved_trace_id = trace_id or get_trace_id() or ""
    logger.info("celery_ping_started")
    log_action(
        action="celery.ping.succeeded",
        entity_type="celery_task",
        entity_id="core.ping",
        trace_id=resolved_trace_id,
        payload={"result": "pong"},
    )
    return "pong"
