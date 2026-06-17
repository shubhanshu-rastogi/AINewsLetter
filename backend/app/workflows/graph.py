"""LangGraph workflow builder + human-in-the-loop resume logic.

The graph pauses *after* ``human_review_node`` (compiled with
``interrupt_after``). Resuming is done by updating the checkpointed state with
the review decision and invoking the graph again with ``None``.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.workflows.nodes import NODE_LOGIC, LogicFn, make_node
from app.workflows.routing import route_approval, route_editorial, route_linear
from app.workflows.state import Nodes, WorkflowState

logger = get_logger("workflow")

# Linear chain (each hop is conditional so failures divert to the error handler).
_LINEAR_EDGES: list[tuple[str, str]] = [
    (Nodes.START, Nodes.SOURCE_COLLECTION),
    (Nodes.SOURCE_COLLECTION, Nodes.RELEVANCE_FILTER),
    (Nodes.RELEVANCE_FILTER, Nodes.CATEGORIZATION),
    (Nodes.CATEGORIZATION, Nodes.FACT_CHECK),
    (Nodes.FACT_CHECK, Nodes.NEWSLETTER_WRITER),
    (Nodes.NEWSLETTER_WRITER, Nodes.LINKEDIN_WRITER),
    (Nodes.LINKEDIN_WRITER, Nodes.VISUAL_GENERATION),
    (Nodes.VISUAL_GENERATION, Nodes.EDITORIAL_REVIEW),
    (Nodes.HUMAN_REVIEW, Nodes.APPROVAL_ROUTER),
    (Nodes.DRAFT_REGENERATION, Nodes.EDITORIAL_REVIEW),
    (Nodes.FEEDBACK_PROCESSOR, Nodes.DRAFT_REGENERATION),
    (Nodes.PUBLISHER, Nodes.COMPLETION),
]


def build_newsletter_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    node_logic: dict[str, LogicFn] | None = None,
):
    """Build and compile the newsletter workflow graph.

    Args:
        checkpointer: state store enabling pause/resume. Defaults to an
            in-process ``MemorySaver``.
        node_logic: optional override of the node registry (used by tests to
            inject failures).
    """
    logic = node_logic or NODE_LOGIC
    builder = StateGraph(WorkflowState)

    for name, fn in logic.items():
        builder.add_node(name, make_node(name, fn))

    builder.add_edge(START, Nodes.START)

    for source, target in _LINEAR_EDGES:
        builder.add_conditional_edges(
            source,
            route_linear(target),
            {target: target, Nodes.ERROR_HANDLER: Nodes.ERROR_HANDLER},
        )

    builder.add_conditional_edges(
        Nodes.EDITORIAL_REVIEW,
        route_editorial,
        {
            Nodes.HUMAN_REVIEW: Nodes.HUMAN_REVIEW,
            Nodes.DRAFT_REGENERATION: Nodes.DRAFT_REGENERATION,
            Nodes.ERROR_HANDLER: Nodes.ERROR_HANDLER,
        },
    )
    builder.add_conditional_edges(
        Nodes.APPROVAL_ROUTER,
        route_approval,
        {
            Nodes.PUBLISHER: Nodes.PUBLISHER,
            Nodes.FEEDBACK_PROCESSOR: Nodes.FEEDBACK_PROCESSOR,
            Nodes.COMPLETION: Nodes.COMPLETION,
            Nodes.ERROR_HANDLER: Nodes.ERROR_HANDLER,
        },
    )

    builder.add_edge(Nodes.COMPLETION, END)
    builder.add_edge(Nodes.ERROR_HANDLER, END)

    return builder.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_after=[Nodes.HUMAN_REVIEW],
    )


def thread_config(workflow_run_id: str) -> dict[str, Any]:
    """Build the LangGraph config that scopes a run to its checkpoint thread."""
    return {"configurable": {"thread_id": workflow_run_id}}


async def resume_workflow_after_review(
    graph,
    workflow_run_id: str,
    review_session_id: str | None,
    approval_status: str,
    feedback_items: list[dict[str, Any]] | None = None,
) -> WorkflowState:
    """Resume a paused workflow from the human-review checkpoint.

    Updates the checkpointed state with the review decision, then continues
    execution (``ainvoke(None, ...)``).
    """
    config = thread_config(workflow_run_id)
    await graph.aupdate_state(
        config,
        {
            "approval_status": approval_status,
            "feedback_items": feedback_items or [],
            "review_session_id": review_session_id,
        },
    )
    logger.info(
        "workflow_resumed",
        workflow_run_id=workflow_run_id,
        approval_status=approval_status,
    )
    return await graph.ainvoke(None, config)
