"""Celery tasks for source file parsing."""
from celery import shared_task

from core.logging import get_logger

logger = get_logger("sources.tasks")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def parse_source_file(self, source_id: str) -> None:
    """Background parse of uploaded Excel/CSV source file."""
    from sources.services.parsing import run_parse

    logger.info("source_parse_task_started", source_file_id=source_id, task_id=self.request.id)
    run_parse(source_id)
    logger.info("source_parse_task_finished", source_file_id=source_id, task_id=self.request.id)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def refresh_google_sheet_snapshot(self, source_id: str) -> None:
    """Background refresh of Google Sheets snapshot."""
    from sources.services.google_snapshot import run_snapshot

    logger.info(
        "google_sheet_snapshot_task_started",
        google_sheet_source_id=source_id,
        task_id=self.request.id,
    )
    run_snapshot(source_id)
    logger.info(
        "google_sheet_snapshot_task_finished",
        google_sheet_source_id=source_id,
        task_id=self.request.id,
    )
