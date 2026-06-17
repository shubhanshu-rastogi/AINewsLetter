"""Review session and feedback schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import FeedbackType, ResolutionStatus, ReviewStatus
from app.schemas.common import ORMModel


# --- Feedback ---
class FeedbackCreate(BaseModel):
    review_session_id: uuid.UUID
    feedback_type: FeedbackType = FeedbackType.GENERAL
    feedback_text: str | None = None
    resolution_status: ResolutionStatus = ResolutionStatus.OPEN


class FeedbackRead(ORMModel):
    id: uuid.UUID
    review_session_id: uuid.UUID
    feedback_type: FeedbackType
    feedback_text: str | None
    resolution_status: ResolutionStatus


# --- Review session ---
class ReviewCreate(BaseModel):
    newsletter_id: uuid.UUID
    reviewer: str | None = Field(default=None, max_length=255)
    review_status: ReviewStatus = ReviewStatus.PENDING
    comments: str | None = None


class ReviewUpdate(BaseModel):
    review_status: ReviewStatus | None = None
    comments: str | None = None


class ReviewRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    reviewer: str | None
    review_status: ReviewStatus
    comments: str | None
    created_at: datetime
