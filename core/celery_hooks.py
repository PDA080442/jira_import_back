from celery.signals import task_failure, task_postrun, task_prerun

from core.context import generate_trace_id, set_trace_id
from core.logging import get_logger

logger = get_logger(__name__)


def _extract_trace_id(task, kwargs) -> str:
    headers = getattr(task.request, "headers", None) or {}
    trace_id = headers.get("trace_id") or kwargs.get("trace_id")
    if trace_id:
        return str(trace_id)
    return generate_trace_id()


@task_prerun.connect
def bind_trace_id_task_prerun(sender=None, task_id=None, task=None, kwargs=None, **extra):
    trace_id = _extract_trace_id(task, kwargs or {})
    set_trace_id(trace_id)
    logger.info(
        "celery_task_started",
        task_name=sender.name if sender else None,
        task_id=task_id,
    )


@task_postrun.connect
def clear_trace_id_task_postrun(sender=None, task_id=None, **extra):
    logger.info(
        "celery_task_finished",
        task_name=sender.name if sender else None,
        task_id=task_id,
    )
    set_trace_id(None)


@task_failure.connect
def log_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    kwargs=None,
    **extra,
):
    from audit.services.log_action import log_action

    trace_id = _extract_trace_id(sender, kwargs or {})
    set_trace_id(trace_id)
    log_action(
        action="celery.task.failed",
        entity_type="celery_task",
        entity_id=sender.name if sender else "",
        trace_id=trace_id,
        payload={
            "task_id": task_id,
            "error": str(exception),
        },
    )
    logger.error(
        "celery_task_failed",
        task_name=sender.name if sender else None,
        task_id=task_id,
        error=str(exception),
    )
