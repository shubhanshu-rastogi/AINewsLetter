"""Workflow service - orchestrates graph invocation + DB bootstrapping.

Holds a compiled graph (with its checkpointer) and a session factory. The
session factory is published to nodes via a ContextVar around each invocation.

Runs execute in the background so the API can return immediately and the UI can
poll :meth:`WorkflowService.get_status` for live stage progress.
"""

from __future__ import annotations

import asyncio
import uuid
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


# --------------------------------------------------------------------------- #
# Stage model (drives the UI progress bar / stepper)
# --------------------------------------------------------------------------- #
STAGE_ORDER: list[str] = [
    Nodes.SOURCE_COLLECTION,
    Nodes.RELEVANCE_FILTER,
    Nodes.CATEGORIZATION,
    Nodes.FACT_CHECK,
    Nodes.NEWSLETTER_WRITER,
    Nodes.LINKEDIN_WRITER,
    Nodes.VISUAL_GENERATION,
    Nodes.EDITORIAL_REVIEW,
    Nodes.HUMAN_REVIEW,
    Nodes.PUBLISHER,
    Nodes.COMPLETION,
]
STAGE_LABELS: dict[str, str] = {
    Nodes.SOURCE_COLLECTION: "Collecting sources",
    Nodes.RELEVANCE_FILTER: "Filtering relevance",
    Nodes.CATEGORIZATION: "Categorizing",
    Nodes.FACT_CHECK: "Fact-checking",
    Nodes.NEWSLETTER_WRITER: "Writing newsletter",
    Nodes.LINKEDIN_WRITER: "Writing LinkedIn post",
    Nodes.VISUAL_GENERATION: "Generating visuals",
    Nodes.EDITORIAL_REVIEW: "Editorial review",
    Nodes.HUMAN_REVIEW: "Human review",
    Nodes.PUBLISHER: "Publishing",
    Nodes.COMPLETION: "Completed",
}
_STAGE_INDEX = {node: i for i, node in enumerate(STAGE_ORDER)}
# Internal nodes map onto the nearest visible stage.
_STAGE_ALIAS: dict[str, str | None] = {
    Nodes.START: None,
    Nodes.APPROVAL_ROUTER: Nodes.HUMAN_REVIEW,
    Nodes.FEEDBACK_PROCESSOR: Nodes.EDITORIAL_REVIEW,
    Nodes.DRAFT_REGENERATION: Nodes.EDITORIAL_REVIEW,
    Nodes.ERROR_HANDLER: None,
}


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


def _stage_view(values: dict[str, Any], next_nodes: list[str], running: bool) -> dict[str, Any]:
    """Derive run_state, progress %, and the per-stage stepper for the UI."""
    cur = values.get("current_step")
    errors = values.get("errors") or []
    approval = values.get("approval_status")
    failed = bool(errors) or cur == Nodes.ERROR_HANDLER
    # A run paused at review whose resume task is active counts as running again.
    paused = (Nodes.APPROVAL_ROUTER in next_nodes) and not running

    if failed:
        run_state = "failed"
    elif paused:
        run_state = "awaiting_review"
    elif cur == Nodes.COMPLETION:
        run_state = "rejected" if approval == Approval.REJECTED else "completed"
    elif running or next_nodes:
        run_state = "running"
    else:
        run_state = "completed"

    terminal = run_state in ("completed", "rejected")
    if cur == Nodes.COMPLETION or terminal:
        cur_idx = len(STAGE_ORDER) - 1
    elif paused:
        cur_idx = _STAGE_INDEX[Nodes.HUMAN_REVIEW]
    else:
        stage = _STAGE_ALIAS.get(cur, cur)
        cur_idx = _STAGE_INDEX.get(stage, -1)

    stages = []
    for i, node in enumerate(STAGE_ORDER):
        if terminal:
            state = "done"
        elif i < cur_idx:
            state = "done"
        elif i == cur_idx:
            state = "failed" if failed else "active"
        else:
            state = "pending"
        stages.append({"key": node, "label": STAGE_LABELS[node], "state": state})

    if terminal:
        progress = 100
    elif cur_idx < 0:
        progress = 0
    else:
        progress = round((cur_idx + 1) / len(STAGE_ORDER) * 100)

    current_label = STAGE_LABELS.get(_STAGE_ALIAS.get(cur, cur) or "", None)
    return {
        "run_state": run_state,
        "progress_percent": progress,
        "stages": stages,
        "current_stage": current_label or (cur or "Starting"),
    }


class WorkflowService:
    def __init__(self, graph, session_factory: SessionFactory) -> None:
        self.graph = graph
        self.session_factory = session_factory
        self._tasks: dict[str, asyncio.Task] = {}

    async def _with_session_factory(self, coro_factory):
        token = set_session_factory(self.session_factory)
        try:
            return await coro_factory()
        finally:
            reset_session_factory(token)

    def _is_running(self, workflow_run_id: str) -> bool:
        task = self._tasks.get(workflow_run_id)
        return task is not None and not task.done()

    async def _create_run(self) -> tuple[str, str, int]:
        """Create the newsletter + workflow_run rows; return their ids."""
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
            return str(workflow_run.id), str(newsletter.id), issue_number

    async def _run_graph(self, wf_id: str, nl_id: str, issue_number: int) -> None:
        try:
            await self._with_session_factory(
                lambda: self.graph.ainvoke(_initial_state(wf_id, nl_id, issue_number), thread_config(wf_id))
            )
        except Exception as exc:  # pragma: no cover - background safety net
            logger.error("workflow_run_failed", workflow_run_id=wf_id, error=str(exc))

    async def start_newsletter_workflow(self) -> dict[str, Any]:
        """Run to the first interrupt (human review) and return the final state.

        Synchronous; used by tests and callers that want the paused state
        directly. The API uses :meth:`start_newsletter_workflow_background`.
        """
        wf_id, nl_id, issue_number = await self._create_run()
        logger.info("workflow_started", workflow_run_id=wf_id, issue_number=issue_number)
        state = await self._with_session_factory(
            lambda: self.graph.ainvoke(_initial_state(wf_id, nl_id, issue_number), thread_config(wf_id))
        )
        return {
            "workflow_run_id": wf_id,
            "newsletter_id": nl_id,
            "issue_number": issue_number,
            "state": state,
            "paused": await self._is_paused(wf_id),
        }

    async def start_newsletter_workflow_background(self) -> dict[str, Any]:
        """Kick off a run on the event loop and return immediately (used by API).

        The UI polls :meth:`get_status` for live stage progress while the run
        advances in the background.
        """
        wf_id, nl_id, issue_number = await self._create_run()
        logger.info("workflow_started", workflow_run_id=wf_id, issue_number=issue_number)
        self._tasks[wf_id] = asyncio.create_task(self._run_graph(wf_id, nl_id, issue_number))
        return {
            "workflow_run_id": wf_id,
            "newsletter_id": nl_id,
            "issue_number": issue_number,
            "current_step": "created",
            "approval_status": Approval.PENDING,
            "publish_status": "pending",
            "paused": False,
            "run_state": "running",
        }

    async def _snapshot(self, workflow_run_id: str):
        return await self.graph.aget_state(thread_config(workflow_run_id))

    async def _is_paused(self, workflow_run_id: str) -> bool:
        snapshot = await self._snapshot(workflow_run_id)
        return bool(snapshot and Nodes.APPROVAL_ROUTER in (snapshot.next or ()))

    async def _status_from_db(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Fallback when no in-memory checkpoint exists yet (or after restart)."""
        try:
            run_uuid = uuid.UUID(workflow_run_id)
        except ValueError:
            return None
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, run_uuid)
            if run is None:
                return None
            nl_id = str(run.newsletter_id) if run.newsletter_id else None
            db_state = {
                ExecutionStatus.SUCCESS: "completed",
                ExecutionStatus.FAILED: "failed",
            }.get(run.workflow_status, "running")
        running = self._is_running(workflow_run_id)
        run_state = "running" if running else db_state
        terminal = run_state in ("completed", "failed")
        stages = [
            {"key": n, "label": STAGE_LABELS[n], "state": ("done" if terminal and run_state == "completed" else "pending")}
            for n in STAGE_ORDER
        ]
        return {
            "workflow_run_id": workflow_run_id,
            "newsletter_id": nl_id,
            "current_step": "created",
            "approval_status": Approval.PENDING,
            "publish_status": "pending",
            "review_session_id": None,
            "errors": [],
            "next": [],
            "paused": False,
            "run_state": run_state,
            "progress_percent": 100 if run_state == "completed" else 0,
            "stages": stages,
            "current_stage": "Starting" if run_state == "running" else run_state.title(),
        }

    async def get_status(self, workflow_run_id: str) -> dict[str, Any] | None:
        snapshot = await self._snapshot(workflow_run_id)
        if not snapshot or not snapshot.values:
            return await self._status_from_db(workflow_run_id)
        values = snapshot.values
        next_nodes = list(snapshot.next or ())
        view = _stage_view(values, next_nodes, self._is_running(workflow_run_id))
        return {
            "workflow_run_id": workflow_run_id,
            "newsletter_id": values.get("newsletter_id"),
            "current_step": values.get("current_step"),
            "approval_status": values.get("approval_status"),
            "publish_status": values.get("publish_status"),
            "review_session_id": values.get("review_session_id"),
            "errors": values.get("errors") or [],
            "next": next_nodes,
            "paused": view["run_state"] == "awaiting_review",
            **view,
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

    async def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent runs joined with their newsletter (durable history)."""
        async with self.session_factory() as session:
            stmt = (
                select(WorkflowRun, Newsletter)
                .join(Newsletter, WorkflowRun.newsletter_id == Newsletter.id, isouter=True)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
        out: list[dict[str, Any]] = []
        for run, nl in rows:
            wf_id = str(run.id)
            running = self._is_running(wf_id)
            db_state = {
                ExecutionStatus.SUCCESS: "completed",
                ExecutionStatus.FAILED: "failed",
                ExecutionStatus.RUNNING: "running",
            }.get(run.workflow_status, "pending")
            out.append(
                {
                    "workflow_run_id": wf_id,
                    "newsletter_id": str(nl.id) if nl else None,
                    "issue_number": nl.issue_number if nl else None,
                    "title": nl.title if nl else None,
                    "newsletter_status": (nl.status.value if nl and nl.status else None),
                    "run_state": "running" if running else db_state,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                }
            )
        return out


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
