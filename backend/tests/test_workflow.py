"""LangGraph workflow orchestration tests (placeholder nodes)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.feedback_item import FeedbackItem
from app.models.publication_record import PublicationRecord
from app.workflows.service import WorkflowService


async def test_workflow_starts_successfully(workflow_service: WorkflowService) -> None:
    result = await workflow_service.start_newsletter_workflow()
    assert result["workflow_run_id"]
    assert result["newsletter_id"]
    assert result["issue_number"] >= 1
    assert result["state"] is not None


async def test_all_nodes_execute_up_to_human_review(
    workflow_service: WorkflowService,
) -> None:
    result = await workflow_service.start_newsletter_workflow()
    state = result["state"]

    # Pipeline produced placeholder outputs at each stage.
    assert state["collected_article_ids"]
    assert state["selected_article_ids"]
    assert state["category_map"]
    assert state["fact_check_results"]
    assert state["newsletter_draft"] is not None
    assert state["linkedin_draft"] is not None
    assert state["visual_ids"]
    assert state["current_step"] == "human_review_node"


async def test_workflow_pauses_at_human_review(
    workflow_service: WorkflowService,
) -> None:
    result = await workflow_service.start_newsletter_workflow()
    status = await workflow_service.get_status(result["workflow_run_id"])

    assert status is not None
    assert status["paused"] is True
    assert "approval_router_node" in status["next"]
    assert status["approval_status"] == "pending"
    assert status["publish_status"] == "pending"  # not yet published
    assert status["review_session_id"]


async def test_human_approval_resumes_and_publishes(
    workflow_service: WorkflowService,
) -> None:
    result = await workflow_service.start_newsletter_workflow()
    wf_id = result["workflow_run_id"]

    status = await workflow_service.submit_review(wf_id, "approved", [])
    assert status is not None
    assert status["current_step"] == "completion_node"
    assert status["publish_status"] == "published"
    assert status["paused"] is False

    async with workflow_service.session_factory() as s:
        count = await s.scalar(select(func.count()).select_from(PublicationRecord))
    assert count == 3  # beehiiv + linkedin + email


async def test_feedback_routes_to_feedback_processor(
    workflow_service: WorkflowService,
) -> None:
    result = await workflow_service.start_newsletter_workflow()
    wf_id = result["workflow_run_id"]

    status = await workflow_service.submit_review(
        wf_id,
        "feedback_required",
        [{"feedback_type": "tone", "feedback_text": "Make it punchier."}],
    )
    assert status is not None
    # Feedback loop regenerates and pauses again at human review.
    assert status["current_step"] == "human_review_node"
    assert status["paused"] is True

    state = await workflow_service.get_state(wf_id)
    assert state["regeneration_count"] >= 1

    async with workflow_service.session_factory() as s:
        feedback_count = await s.scalar(select(func.count()).select_from(FeedbackItem))
    assert feedback_count == 1


async def test_rejected_review_completes_without_publishing(
    workflow_service: WorkflowService,
) -> None:
    result = await workflow_service.start_newsletter_workflow()
    wf_id = result["workflow_run_id"]

    status = await workflow_service.submit_review(wf_id, "rejected", [])
    assert status is not None
    assert status["current_step"] == "completion_node"
    assert status["publish_status"] == "rejected"
    assert status["paused"] is False

    async with workflow_service.session_factory() as s:
        count = await s.scalar(select(func.count()).select_from(PublicationRecord))
    assert count == 0  # nothing published


async def test_node_failure_routes_to_error_handler(session_factory) -> None:
    from langgraph.checkpoint.memory import MemorySaver

    from app.workflows.graph import build_newsletter_graph
    from app.workflows.nodes import NODE_LOGIC
    from app.workflows.state import Nodes

    async def boom(state):
        raise RuntimeError("boom")

    logic = {**NODE_LOGIC, Nodes.SOURCE_COLLECTION: boom}
    service = WorkflowService(
        build_newsletter_graph(checkpointer=MemorySaver(), node_logic=logic),
        session_factory,
    )

    result = await service.start_newsletter_workflow()
    status = await service.get_status(result["workflow_run_id"])
    assert status is not None
    assert status["current_step"] == "error_handler_node"
    assert status["publish_status"] == "skipped"
    assert any("boom" in e for e in status["errors"])
