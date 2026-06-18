"""Placeholder LangGraph node implementations.

Each public node is built by wrapping a small async "logic" function with
:func:`make_node`, which adds structured logging, ``agent_runs`` tracking,
``current_step`` updates, and clean exception handling (failures set the
``failed`` flag so routing can divert to the error handler).

NO real AI / collection / publishing logic lives here yet - outputs are stubs.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.models.agent_run import AgentRun
from app.models.enums import (
    ExecutionStatus,
    NewsletterStatus,
    PublicationChannel,
    PublicationStatus,
    ReviewStatus,
)
from app.models.feedback_item import FeedbackItem
from app.models.newsletter import Newsletter
from app.models.publication_record import PublicationRecord
from app.models.review_session import ReviewSession
from app.models.workflow_run import WorkflowRun
from app.workflows.runtime import get_session_factory
from app.workflows.state import Approval, Nodes, WorkflowState

logger = get_logger("workflow")

LogicFn = Callable[[WorkflowState], Awaitable[dict[str, Any]]]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


async def _update_workflow_run(wf_id: str | None, **fields: Any) -> None:
    wf_uuid = _as_uuid(wf_id)
    if wf_uuid is None:
        return
    sf = get_session_factory()
    async with sf() as session:
        run = await session.get(WorkflowRun, wf_uuid)
        if run is not None:
            for key, value in fields.items():
                setattr(run, key, value)
            await session.commit()


async def _set_newsletter_status(nl_id: str | None, status: NewsletterStatus) -> None:
    nl_uuid = _as_uuid(nl_id)
    if nl_uuid is None:
        return
    sf = get_session_factory()
    async with sf() as session:
        newsletter = await session.get(Newsletter, nl_uuid)
        if newsletter is not None:
            newsletter.status = status
            await session.commit()


# --------------------------------------------------------------------------- #
# Node wrapper (logging + agent_runs + error handling)
# --------------------------------------------------------------------------- #
def make_node(name: str, fn: LogicFn) -> Callable[[WorkflowState], Awaitable[dict[str, Any]]]:
    async def node(state: WorkflowState) -> dict[str, Any]:
        wf_id = state.get("workflow_run_id")
        started_at = _utcnow()
        perf_start = time.perf_counter()
        agent_run_id = await _start_agent_run(name, wf_id, started_at)

        logger.info("node_started", node=name, workflow_run_id=wf_id)
        try:
            updates = await fn(state) or {}
            updates["current_step"] = name
            updates["updated_at"] = _utcnow().isoformat()
            await _finish_agent_run(
                agent_run_id, ExecutionStatus.SUCCESS, perf_start, None
            )
            logger.info("node_completed", node=name, workflow_run_id=wf_id)
            return updates
        except Exception as exc:  # noqa: BLE001 - deliberate: route failures, don't crash
            await _finish_agent_run(
                agent_run_id, ExecutionStatus.FAILED, perf_start, str(exc)
            )
            logger.error("node_failed", node=name, workflow_run_id=wf_id, error=str(exc))
            errors = list(state.get("errors") or []) + [f"{name}: {exc}"]
            return {
                "errors": errors,
                "failed": True,
                "current_step": name,
                "updated_at": _utcnow().isoformat(),
            }

    node.__name__ = name
    return node


async def _start_agent_run(
    name: str, wf_id: str | None, started_at: datetime
) -> uuid.UUID | None:
    """Best-effort agent_run creation; never fails the workflow."""
    try:
        sf = get_session_factory()
        async with sf() as session:
            run = AgentRun(
                agent_name=name,
                execution_status=ExecutionStatus.RUNNING,
                started_at=started_at,
                workflow_run_id=_as_uuid(wf_id),
            )
            session.add(run)
            await session.commit()
            return run.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_run_tracking_failed", node=name, error=str(exc))
        return None


async def _finish_agent_run(
    agent_run_id: uuid.UUID | None,
    status: ExecutionStatus,
    perf_start: float,
    error_message: str | None,
) -> None:
    if agent_run_id is None:
        return
    try:
        sf = get_session_factory()
        async with sf() as session:
            run = await session.get(AgentRun, agent_run_id)
            if run is not None:
                run.execution_status = status
                run.finished_at = _utcnow()
                run.execution_time = round(time.perf_counter() - perf_start, 4)
                run.error_message = error_message
                await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_run_finish_failed", error=str(exc))


# --------------------------------------------------------------------------- #
# Node logic (placeholders only)
# --------------------------------------------------------------------------- #
async def _start(state: WorkflowState) -> dict[str, Any]:
    await _update_workflow_run(
        state.get("workflow_run_id"),
        workflow_status=ExecutionStatus.RUNNING,
        started_at=_utcnow(),
    )
    return {"approval_status": Approval.PENDING, "publish_status": "pending"}


async def _source_collection(state: WorkflowState) -> dict[str, Any]:
    """Collect content from active sources via the SourceCollectionAgent.

    Reads active sources (prioritized by the strategy layer), runs collection,
    persists articles, and records the new article ids on the state. Individual
    source failures are handled inside the agent and do not fail the workflow.
    """
    from app.agents.source_collection.collector import SourceCollectionAgent

    agent = SourceCollectionAgent(get_session_factory())
    article_ids = await agent.collect_all_sources()
    return {"collected_article_ids": article_ids}


async def _relevance_filter(state: WorkflowState) -> dict[str, Any]:
    """Score, dedup, rank, and select the collected articles."""
    from app.agents.relevance_filter.filter_agent import RelevanceFilterAgent

    agent = RelevanceFilterAgent(get_session_factory())
    result = await agent.run(state.get("collected_article_ids") or [])
    return {
        "selected_article_ids": result["selected_article_ids"],
        "category_map": result["category_map"],
    }


async def _categorization(state: WorkflowState) -> dict[str, Any]:
    """Classify and tag the selected articles, refining the category map."""
    from app.agents.categorization.categorization_agent import CategorizationAgent

    agent = CategorizationAgent(get_session_factory())
    result = await agent.run(state.get("selected_article_ids") or [])
    return {"category_map": result["category_map"]}


async def _fact_check(state: WorkflowState) -> dict[str, Any]:
    """Verify selected articles, build evidence, and drop REJECTED ones."""
    from app.agents.fact_checking.fact_check_agent import FactCheckAgent

    agent = FactCheckAgent(get_session_factory())
    result = await agent.run(state.get("selected_article_ids") or [])
    return {
        "fact_check_results": result["fact_check_results"],
        "selected_article_ids": result["selected_article_ids"],  # rejected removed
    }


async def _newsletter_writer(state: WorkflowState) -> dict[str, Any]:
    """Generate the newsletter (+ LinkedIn + carousel) from verified articles."""
    from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent

    agent = NewsletterWriterAgent(get_session_factory())
    result = await agent.generate_newsletter(
        article_ids=state.get("selected_article_ids") or [],
        newsletter_id=state.get("newsletter_id"),
    )
    return {
        "newsletter_draft": result["content"],
        "linkedin_draft": {"body": result["linkedin_post"], "carousel": result["carousel"]},
    }


async def _linkedin_writer(state: WorkflowState) -> dict[str, Any]:
    # The newsletter writer already produced LinkedIn content; preserve it.
    if state.get("linkedin_draft"):
        return {}
    return {"linkedin_draft": {"body": "placeholder LinkedIn post"}}


async def _visual_generation(state: WorkflowState) -> dict[str, Any]:
    return {"visual_ids": ["visual-stub-1"]}


async def _editorial_review(state: WorkflowState) -> dict[str, Any]:
    # Placeholder editorial check: always passes for now.
    return {"editorial_passed": True}


async def _human_review(state: WorkflowState) -> dict[str, Any]:
    """Create a review session, mark the newsletter as 'review', and pause.

    The graph is compiled with ``interrupt_after`` on this node, so execution
    stops here until :func:`resume_workflow_after_review` is called.
    """
    nl_id = state.get("newsletter_id")
    review_session_id: str | None = None

    sf = get_session_factory()
    async with sf() as session:
        review = ReviewSession(
            newsletter_id=_as_uuid(nl_id),
            review_status=ReviewStatus.PENDING,
        )
        session.add(review)
        await session.commit()
        review_session_id = str(review.id)

    await _set_newsletter_status(nl_id, NewsletterStatus.REVIEW)
    logger.info(
        "workflow_paused_for_review",
        workflow_run_id=state.get("workflow_run_id"),
        review_session_id=review_session_id,
    )
    return {
        "review_session_id": review_session_id,
        "approval_status": Approval.PENDING,
    }


async def _approval_router(state: WorkflowState) -> dict[str, Any]:
    # Routing happens on the outgoing conditional edge; this node only marks
    # the decision point in the trace.
    logger.info(
        "approval_decision",
        workflow_run_id=state.get("workflow_run_id"),
        approval_status=state.get("approval_status"),
    )
    return {}


async def _feedback_processor(state: WorkflowState) -> dict[str, Any]:
    review_session_id = state.get("review_session_id")
    items = state.get("feedback_items") or []
    if review_session_id and items:
        sf = get_session_factory()
        async with sf() as session:
            for item in items:
                session.add(
                    FeedbackItem(
                        review_session_id=_as_uuid(review_session_id),
                        feedback_text=item.get("feedback_text"),
                    )
                )
            await session.commit()
    # Reset approval for the next review round.
    return {"approval_status": Approval.PENDING}


async def _draft_regeneration(state: WorkflowState) -> dict[str, Any]:
    count = (state.get("regeneration_count") or 0) + 1
    draft = dict(state.get("newsletter_draft") or {})
    draft["revised"] = True
    draft["revision"] = count
    return {"newsletter_draft": draft, "regeneration_count": count}


async def _publisher(state: WorkflowState) -> dict[str, Any]:
    nl_id = state.get("newsletter_id")
    sf = get_session_factory()
    async with sf() as session:
        for channel in (
            PublicationChannel.BEEHIIV,
            PublicationChannel.LINKEDIN,
            PublicationChannel.EMAIL,
        ):
            session.add(
                PublicationRecord(
                    newsletter_id=_as_uuid(nl_id),
                    channel=channel,
                    publication_status=PublicationStatus.PUBLISHED,
                    publication_date=_utcnow(),
                )
            )
        await session.commit()

    await _set_newsletter_status(nl_id, NewsletterStatus.PUBLISHED)
    return {"publish_status": "published"}


async def _completion(state: WorkflowState) -> dict[str, Any]:
    rejected = state.get("approval_status") == Approval.REJECTED
    if rejected:
        await _set_newsletter_status(state.get("newsletter_id"), NewsletterStatus.ARCHIVED)

    await _update_workflow_run(
        state.get("workflow_run_id"),
        workflow_status=ExecutionStatus.SUCCESS,
        finished_at=_utcnow(),
    )
    logger.info("workflow_completed", workflow_run_id=state.get("workflow_run_id"))
    return {"publish_status": "rejected" if rejected else state.get("publish_status")}


async def _error_handler(state: WorkflowState) -> dict[str, Any]:
    await _update_workflow_run(
        state.get("workflow_run_id"),
        workflow_status=ExecutionStatus.FAILED,
        finished_at=_utcnow(),
    )
    logger.error(
        "workflow_failed",
        workflow_run_id=state.get("workflow_run_id"),
        errors=state.get("errors"),
    )
    return {"publish_status": "skipped"}


# Registry: node name -> raw logic function. The builder wraps each with
# make_node(). Tests may pass an alternative registry to inject failures.
NODE_LOGIC: dict[str, LogicFn] = {
    Nodes.START: _start,
    Nodes.SOURCE_COLLECTION: _source_collection,
    Nodes.RELEVANCE_FILTER: _relevance_filter,
    Nodes.CATEGORIZATION: _categorization,
    Nodes.FACT_CHECK: _fact_check,
    Nodes.NEWSLETTER_WRITER: _newsletter_writer,
    Nodes.LINKEDIN_WRITER: _linkedin_writer,
    Nodes.VISUAL_GENERATION: _visual_generation,
    Nodes.EDITORIAL_REVIEW: _editorial_review,
    Nodes.HUMAN_REVIEW: _human_review,
    Nodes.APPROVAL_ROUTER: _approval_router,
    Nodes.FEEDBACK_PROCESSOR: _feedback_processor,
    Nodes.DRAFT_REGENERATION: _draft_regeneration,
    Nodes.PUBLISHER: _publisher,
    Nodes.COMPLETION: _completion,
    Nodes.ERROR_HANDLER: _error_handler,
}
