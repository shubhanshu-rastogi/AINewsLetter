"""Workflow service - orchestrates graph invocation + DB bootstrapping.

Holds a compiled graph (with its checkpointer) and a session factory. The
session factory is published to nodes via a ContextVar around each invocation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.models.enums import ExecutionStatus, NewsletterStatus
from app.models.newsletter import Newsletter
from app.models.workflow_run import WorkflowRun
from app.workflows.graph import (
    build_newsletter_graph,
    resume_workflow_after_review,
    thread_config,
)
from app.workflows.runtime import (
    SessionFactory,
    reset_session_factory,
    set_session_factory,
)
from app.workflows.state import Approval, Nodes, WorkflowState

logger = get_logger("workflow")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial_state(wf_id: str, nl_id: str, issue_number: int) -> WorkflowState:
    now = _utcnow_iso()
    return {
        "workflow_run_id": wf_id,
        "newsletter_id": nl_id,
        "issue_number": issue_number,
        "collected_article_ids": [],
        "selected_article_ids": [],
        "category_map": {},
        "fact_check_results": [],
        "newsletter_draft": None,
        "linkedin_draft": None,
        "visual_ids": [],
        "review_session_id": None,
        "feedback_items": [],
        "approval_status": Approval.PENDING,
        "publish_status": "pending",
        "errors": [],
        "current_step": "created",
        "created_at": now,
        "updated_at": now,
        "regeneration_count": 0,
    }


class WorkflowService:
    def __init__(self, graph, session_factory: SessionFactory) -> None:
        self.graph = graph
        self.session_factory = session_factory

    async def _with_session_factory(self, coro_factory):
        token = set_session_factory(self.session_factory)
        try:
            return await coro_factory()
        finally:
            reset_session_factory(token)

    async def start_newsletter_workflow(self) -> dict[str, Any]:
        # Create the workflow_run + newsletter first so we have a stable
        # thread id and IDs to return immediately.
        async with self.session_factory() as session:
            max_issue = await session.scalar(select(func.max(Newsletter.issue_number)))
            issue_number = (max_issue or 0) + 1
            newsletter = Newsletter(
                title=f"Weekly AI Newsletter - Issue {issue_number}",
                issue_number=issue_number,
                status=NewsletterStatus.DRAFT,
            )
            session.add(newsletter)
            await session.flush()
            workflow_run = WorkflowRun(
                workflow_name="weekly_newsletter",
                workflow_status=ExecutionStatus.PENDING,
                newsletter_id=newsletter.id,
            )
            session.add(workflow_run)
            await session.commit()
            wf_id = str(workflow_run.id)
            nl_id = str(newsletter.id)

        logger.info("workflow_started", workflow_run_id=wf_id, issue_number=issue_number)
        state = await self._with_session_factory(
            lambda: self.graph.ainvoke(
                _initial_state(wf_id, nl_id, issue_number), thread_config(wf_id)
            )
        )
        return {
            "workflow_run_id": wf_id,
            "newsletter_id": nl_id,
            "issue_number": issue_number,
            "state": state,
            "paused": await self._is_paused(wf_id),
        }

    async def _snapshot(self, workflow_run_id: str):
        return await self.graph.aget_state(thread_config(workflow_run_id))

    async def _is_paused(self, workflow_run_id: str) -> bool:
        snapshot = await self._snapshot(workflow_run_id)
        return bool(snapshot and Nodes.APPROVAL_ROUTER in (snapshot.next or ()))

    async def get_status(self, workflow_run_id: str) -> dict[str, Any] | None:
        snapshot = await self._snapshot(workflow_run_id)
        if not snapshot or not snapshot.values:
            return None
        values = snapshot.values
        next_nodes = list(snapshot.next or ())
        return {
            "workflow_run_id": workflow_run_id,
            "current_step": values.get("current_step"),
            "approval_status": values.get("approval_status"),
            "publish_status": values.get("publish_status"),
            "review_session_id": values.get("review_session_id"),
            "errors": values.get("errors") or [],
            "next": next_nodes,
            "paused": Nodes.APPROVAL_ROUTER in next_nodes,
        }

    async def submit_review(
        self,
        workflow_run_id: str,
        approval_status: str,
        feedback_items: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        snapshot = await self._snapshot(workflow_run_id)
        if not snapshot or not snapshot.values:
            return None
        review_session_id = snapshot.values.get("review_session_id")
        await self._with_session_factory(
            lambda: resume_workflow_after_review(
                self.graph,
                workflow_run_id,
                review_session_id,
                approval_status,
                feedback_items,
            )
        )
        return await self.get_status(workflow_run_id)

    async def get_state(self, workflow_run_id: str) -> dict[str, Any] | None:
        snapshot = await self._snapshot(workflow_run_id)
        if not snapshot or not snapshot.values:
            return None
        return dict(snapshot.values)


# --------------------------------------------------------------------------- #
# Application singleton (production wiring)
# --------------------------------------------------------------------------- #
_service: WorkflowService | None = None


def get_workflow_service() -> WorkflowService:
    """FastAPI dependency: process-wide workflow service.

    Uses an in-process ``MemorySaver`` checkpointer (swap for a Postgres saver
    in multi-process production) and the app's default session factory.
    """
    global _service
    if _service is None:
        from app.db.session import AsyncSessionLocal

        _service = WorkflowService(build_newsletter_graph(), AsyncSessionLocal)
    return _service
