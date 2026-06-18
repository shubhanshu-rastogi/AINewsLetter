"""Approval routing decisions (pure function used by the workflow node)."""

from __future__ import annotations

from app.models.enums import ReviewState

# Workflow node destinations.
TO_PUBLISHER = "publisher_node"
TO_FEEDBACK = "feedback_processor_node"
TO_COMPLETION = "completion_node"


def route_decision(approval_status: str | None) -> str:
    """Map an approval decision to the next workflow node."""
    status = (approval_status or "").lower()
    if status in (ReviewState.APPROVED.value, "approved"):
        return TO_PUBLISHER
    if status in (ReviewState.FEEDBACK_REQUIRED.value, "feedback_required"):
        return TO_FEEDBACK
    if status in (ReviewState.REJECTED.value, "rejected"):
        return TO_COMPLETION
    return TO_COMPLETION
