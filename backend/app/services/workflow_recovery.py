"""Workflow recovery service.

Recovers the system after restarts/failures:
  - surfaces paused review workflows (awaiting human action)
  - drains the publication retry queue
  - marks interrupted (stuck RUNNING) workflow + agent runs as failed so they
    can be restarted
  - ensures the scheduler is running
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import ACTIVE_REVIEW_SESSIONS
from app.models.agent_run import AgentRun
from app.models.enums import ExecutionStatus, ReviewState
from app.models.retry_queue import RetryQueueEntry
from app.models.review_session import ReviewSession
from app.models.workflow_run import WorkflowRun

logger = get_logger("recovery")

STUCK_AFTER = timedelta(hours=2)


class WorkflowRecoveryService:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    async def pending_reviews(self) -> list[str]:
        """Review sessions awaiting a human decision (workflow paused)."""
        async with self.session_factory() as session:
            rows = await session.execute(
                select(ReviewSession.id).where(ReviewSession.review_state == ReviewState.PENDING.value)
            )
            ids = [str(r[0]) for r in rows]
        ACTIVE_REVIEW_SESSIONS.set(len(ids))
        logger.info("recovery_pending_reviews", count=len(ids))
        return ids

    async def recover_failed_publications(self) -> dict[str, int]:
        """Drain pending retry-queue entries via the publisher agent."""
        from app.agents.publishing.publisher_agent import PublisherAgent

        agent = PublisherAgent(self.session_factory)
        async with self.session_factory() as session:
            entries = (
                (await session.execute(select(RetryQueueEntry).where(RetryQueueEntry.status == "pending")))
                .scalars()
                .all()
            )
            targets = [(str(e.id), str(e.publication_record_id)) for e in entries]

        recovered = 0
        abandoned = 0
        for entry_id, record_id in targets:
            try:
                out = await agent.retry_publication(record_id)
                succeeded = (out.get("result") or {}).get("status") == "published"
            except Exception as exc:  # noqa: BLE001
                logger.warning("retry_failed", record_id=record_id, error=str(exc))
                succeeded = False
            async with self.session_factory() as session:
                entry = await session.get(RetryQueueEntry, _uuid(entry_id))
                if entry is None:
                    continue
                if succeeded:
                    entry.status = "done"
                    recovered += 1
                else:
                    entry.attempt += 1
                    if entry.attempt >= entry.max_retries:
                        entry.status = "abandoned"
                        abandoned += 1
                await session.commit()
        logger.info("recovery_publications", recovered=recovered, abandoned=abandoned)
        return {"recovered": recovered, "abandoned": abandoned, "processed": len(targets)}

    async def recover_stuck_workflows(self) -> int:
        """Mark long-running (interrupted) workflow runs as failed."""
        cutoff = datetime.now(timezone.utc) - STUCK_AFTER
        async with self.session_factory() as session:
            result = await session.execute(
                update(WorkflowRun)
                .where(
                    WorkflowRun.workflow_status == ExecutionStatus.RUNNING,
                    WorkflowRun.started_at.is_not(None),
                    WorkflowRun.started_at < cutoff,
                )
                .values(workflow_status=ExecutionStatus.FAILED, finished_at=datetime.now(timezone.utc))
            )
            await session.commit()
            count = result.rowcount or 0
        logger.info("recovery_stuck_workflows", count=count)
        return count

    async def recover_failed_agents(self) -> int:
        """Mark interrupted (stuck RUNNING) agent runs as failed."""
        cutoff = datetime.now(timezone.utc) - STUCK_AFTER
        async with self.session_factory() as session:
            result = await session.execute(
                update(AgentRun)
                .where(
                    AgentRun.execution_status == ExecutionStatus.RUNNING,
                    AgentRun.started_at.is_not(None),
                    AgentRun.started_at < cutoff,
                )
                .values(
                    execution_status=ExecutionStatus.FAILED,
                    finished_at=datetime.now(timezone.utc),
                    error_message="recovered: interrupted run",
                )
            )
            await session.commit()
            count = result.rowcount or 0
        logger.info("recovery_failed_agents", count=count)
        return count

    def ensure_scheduler(self) -> bool:
        from app.core.config import settings

        if not settings.ENABLE_SCHEDULER:
            return False
        from app.agents.source_collection.scheduler import scheduler

        if not scheduler.running:
            scheduler.start()
        return scheduler.running

    async def recover_all(self) -> dict[str, Any]:
        summary = {
            "pending_reviews": await self.pending_reviews(),
            "publications": await self.recover_failed_publications(),
            "stuck_workflows": await self.recover_stuck_workflows(),
            "stuck_agents": await self.recover_failed_agents(),
        }
        logger.info("workflow_recovery_completed")
        return summary


def _uuid(value: str):
    import uuid

    return uuid.UUID(value)
