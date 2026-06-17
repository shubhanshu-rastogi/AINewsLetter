"""APScheduler-based scheduling for collection + the weekly newsletter run.

Schedules:
  - Daily content collection at 08:00 UTC
  - Weekly newsletter workflow every Friday at 06:00 UTC

Overlap is prevented via ``max_instances=1`` + ``coalesce=True``.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logging import get_logger

logger = get_logger("collection.scheduler")

DAILY_COLLECTION_JOB_ID = "daily_source_collection"
WEEKLY_NEWSLETTER_JOB_ID = "weekly_newsletter_run"


async def run_daily_collection() -> None:
    """Job: collect all active sources."""
    from app.agents.source_collection.collector import SourceCollectionAgent
    from app.db.session import AsyncSessionLocal

    logger.info("scheduled_collection_started")
    agent = SourceCollectionAgent(AsyncSessionLocal)
    new_ids = await agent.collect_all_sources()
    logger.info("scheduled_collection_finished", new_articles=len(new_ids))


async def run_weekly_newsletter() -> None:
    """Job: kick off the weekly newsletter workflow."""
    from app.workflows.service import get_workflow_service

    logger.info("scheduled_newsletter_started")
    service = get_workflow_service()
    result = await service.start_newsletter_workflow()
    logger.info("scheduled_newsletter_started_run", workflow_run_id=result["workflow_run_id"])


class CollectionScheduler:
    """Thin wrapper around an AsyncIOScheduler with our two cron jobs."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self) -> None:
        if self.running:
            return
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            run_daily_collection,
            CronTrigger(hour=8, minute=0, timezone="UTC"),
            id=DAILY_COLLECTION_JOB_ID,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            replace_existing=True,
        )
        scheduler.add_job(
            run_weekly_newsletter,
            CronTrigger(day_of_week="fri", hour=6, minute=0, timezone="UTC"),
            id=WEEKLY_NEWSLETTER_JOB_ID,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            replace_existing=True,
        )
        scheduler.start()
        self._scheduler = scheduler
        logger.info(
            "scheduler_started",
            jobs=[DAILY_COLLECTION_JOB_ID, WEEKLY_NEWSLETTER_JOB_ID],
        )

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("scheduler_stopped")


scheduler = CollectionScheduler()
