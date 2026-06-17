"""Conditional routing functions for the workflow graph.

All routers check the ``failed`` flag first so any node failure diverts to the
error handler.
"""

from __future__ import annotations

from app.workflows.state import Approval, Nodes, WorkflowState


def route_linear(normal_next: str):
    """Return a router that goes to ``normal_next`` unless the node failed."""

    def router(state: WorkflowState) -> str:
        if state.get("failed"):
            return Nodes.ERROR_HANDLER
        return normal_next

    return router


def route_editorial(state: WorkflowState) -> str:
    if state.get("failed"):
        return Nodes.ERROR_HANDLER
    if state.get("editorial_passed", True):
        return Nodes.HUMAN_REVIEW
    return Nodes.DRAFT_REGENERATION


def route_approval(state: WorkflowState) -> str:
    if state.get("failed"):
        return Nodes.ERROR_HANDLER
    status = state.get("approval_status")
    if status == Approval.APPROVED:
        return Nodes.PUBLISHER
    if status == Approval.FEEDBACK_REQUIRED:
        return Nodes.FEEDBACK_PROCESSOR
    if status == Approval.REJECTED:
        return Nodes.COMPLETION
    # No valid decision after a resume is unexpected -> treat as error.
    return Nodes.ERROR_HANDLER
