"""Review / feedback API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class FeedbackItemInput(BaseModel):
    # Lenient strings (case-insensitive); the classifier normalizes them.
    artifact_type: str = "newsletter"
    section_name: str | None = None
    feedback_text: str = Field(..., min_length=1)
    severity: str | None = None


class FeedbackRequest(BaseModel):
    feedback_items: list[FeedbackItemInput] = Field(..., min_length=1)


class ApprovalRequest(BaseModel):
    approval_status: str = "APPROVED"
    comments: str | None = None
    reviewer: str | None = None


class RejectionRequest(BaseModel):
    approval_status: str = "REJECTED"
    comments: str | None = None
    reviewer: str | None = None


class RegenerateRequest(BaseModel):
    action_type: str = Field(
        ...,
        description="regenerate_section|regenerate_linkedin|regenerate_carousel_slide|regenerate_cover|replace_article_and_regenerate_section",
    )
    section: str | None = None
    slide_number: int | None = None
    reason: str = "manual regeneration"


class ReviewSessionRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    reviewer: str | None
    review_state: str
    comments: str | None
    notion_page_url: str | None
    version_number: int | None
    approved_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FeedbackItemRead(ORMModel):
    id: uuid.UUID
    feedback_text: str | None
    artifact_type: str | None
    section_name: str | None
    feedback_category: str | None
    severity: str | None
    action_required: str | None
    regeneration_needed: bool | None
    resolution_status: str


class ReviewPackageResponse(BaseModel):
    review_session_id: str
    package: dict[str, Any]


class FeedbackResponse(BaseModel):
    review_session_id: str
    newsletter_id: str
    plan: dict[str, Any]
    changed_sections: list[str]
    new_review_session_id: str | None


class ReviewVersionRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    version_number: int
    feedback_summary: list[Any] | None
    regeneration_plan: dict[str, Any] | None
    changed_sections: list[Any] | None
    reviewer_decision: str | None
    created_at: datetime
