"""Workflow recovery service tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.agent_run import AgentRun
from app.models.enums import (
    ExecutionStatus,
    NewsletterStatus,
    PublicationChannel,
    PublicationStatus,
    PublishState,
    ReviewState,
    ReviewStatus,
)
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.publication_record import PublicationRecord
from app.models.retry_queue import RetryQueueEntry
from app.models.review_session import ReviewSession
from app.models.workflow_run import WorkflowRun
from app.services.workflow_recovery import WorkflowRecoveryService


def _old() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=3)


async def test_pending_reviews(session_factory) -> None:
    async with session_factory() as s:
        nl = Newsletter(title="N", issue_number=1)
        s.add(nl)
        await s.flush()
        s.add(
            ReviewSession(
                newsletter_id=nl.id, review_status=ReviewStatus.PENDING, review_state=ReviewState.PENDING.value
            )
        )
        await s.commit()

    ids = await WorkflowRecoveryService(session_factory).pending_reviews()
    assert len(ids) == 1


async def test_recover_stuck_workflows_and_agents(session_factory) -> None:
    async with session_factory() as s:
        nl = Newsletter(title="N", issue_number=1)
        s.add(nl)
        await s.flush()
        s.add(
            WorkflowRun(
                workflow_name="weekly", workflow_status=ExecutionStatus.RUNNING, started_at=_old(), newsletter_id=nl.id
            )
        )
        s.add(AgentRun(agent_name="writer", execution_status=ExecutionStatus.RUNNING, started_at=_old()))
        await s.commit()

    svc = WorkflowRecoveryService(session_factory)
    assert await svc.recover_stuck_workflows() == 1
    assert await svc.recover_failed_agents() == 1

    async with session_factory() as s:
        wr = (await s.execute(select(WorkflowRun))).scalar_one()
        ar = (await s.execute(select(AgentRun))).scalar_one()
    assert wr.workflow_status == ExecutionStatus.FAILED and wr.finished_at is not None
    assert ar.execution_status == ExecutionStatus.FAILED


async def test_recover_does_not_touch_recent_runs(session_factory) -> None:
    async with session_factory() as s:
        s.add(
            WorkflowRun(
                workflow_name="weekly", workflow_status=ExecutionStatus.RUNNING, started_at=datetime.now(timezone.utc)
            )
        )
        await s.commit()
    assert await WorkflowRecoveryService(session_factory).recover_stuck_workflows() == 0


async def test_recover_failed_publications(session_factory) -> None:
    # Approved newsletter + a failed beehiiv record queued for retry.
    async with session_factory() as s:
        nl = Newsletter(title="N", issue_number=1, status=NewsletterStatus.APPROVED)
        s.add(nl)
        await s.flush()
        s.add(
            NewsletterDraft(
                newsletter_id=nl.id, content={"cover": {"title": "N"}, "top_stories": []}, current_version=1
            )
        )
        s.add(
            ReviewSession(
                newsletter_id=nl.id, review_status=ReviewStatus.APPROVED, review_state=ReviewState.APPROVED.value
            )
        )
        rec = PublicationRecord(
            newsletter_id=nl.id,
            channel=PublicationChannel.BEEHIIV,
            publication_status=PublicationStatus.FAILED,
            publish_state=PublishState.RETRYING.value,
            retry_count=1,
        )
        s.add(rec)
        await s.flush()
        s.add(
            RetryQueueEntry(
                publication_record_id=rec.id,
                newsletter_id=nl.id,
                channel="beehiiv",
                attempt=1,
                max_retries=3,
                status="pending",
            )
        )
        await s.commit()

    result = await WorkflowRecoveryService(session_factory).recover_failed_publications()
    assert result["processed"] == 1
    assert result["recovered"] == 1  # simulated beehiiv publish succeeds

    async with session_factory() as s:
        entry = (await s.execute(select(RetryQueueEntry))).scalar_one()
    assert entry.status == "done"


async def test_recover_all(session_factory) -> None:
    summary = await WorkflowRecoveryService(session_factory).recover_all()
    assert set(summary) == {"pending_reviews", "publications", "stuck_workflows", "stuck_agents"}
