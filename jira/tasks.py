"""Celery tasks for Jira metadata sync."""
from celery import shared_task

from core.logging import get_logger

logger = get_logger("jira.tasks")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def sync_jira_metadata(self, connection_id: str) -> None:
    """Background sync of Jira project metadata for a connection."""
    from jira.services.metadata import run_metadata_sync

    logger.info("jira_metadata_task_started", connection_id=connection_id, task_id=self.request.id)
    run_metadata_sync(connection_id)
    logger.info("jira_metadata_task_finished", connection_id=connection_id, task_id=self.request.id)
