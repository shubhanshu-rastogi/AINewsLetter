"""Workflow API schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import FeedbackType


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FEEDBACK_REQUIRED = "feedback_required"


class FeedbackInput(BaseModel):
    feedback_type: FeedbackType = FeedbackType.GENERAL
    feedback_text: str = Field(..., min_length=1)


class WorkflowStartResponse(BaseModel):
    workflow_run_id: str
    newsletter_id: str
    issue_number: int
    current_step: str | None = None
    approval_status: str | None = None
    publish_status: str | None = None
    paused: bool = False


class WorkflowStatusResponse(BaseModel):
    workflow_run_id: str
    current_step: str | None = None
    approval_status: str | None = None
    publish_status: str | None = None
    review_session_id: str | None = None
    errors: list[str] = []
    next: list[str] = []
    paused: bool = False


class ReviewRequest(BaseModel):
    approval_status: ApprovalDecision
    feedback_items: list[FeedbackInput] = []


class WorkflowStateResponse(BaseModel):
    workflow_run_id: str
    state: dict[str, Any]
