"""Newsletter writer API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GenerateRequest(BaseModel):
    article_ids: list[str] | None = None
    newsletter_id: str | None = None
    created_by: str = "system"


class RegenerateRequest(BaseModel):
    section: str = Field(..., min_length=1)
    reason: str = Field(default="manual regeneration")
    changed_by: str = "system"


class NewsletterGenerateResponse(BaseModel):
    newsletter_id: str
    version: int
    word_count: int
    reading_time_minutes: int
    sections_generated: int
    content: dict[str, Any]


class NewsletterDraftRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    title: str | None
    content: dict[str, Any] | None
    email_subjects: list[str] | None
    word_count: int | None
    reading_time_minutes: int | None
    current_version: int


class NewsletterVersionRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    version_number: int
    word_count: int | None
    created_by: str | None
    change_reason: str | None
    created_at: datetime


class LinkedInPostRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    variant: str | None
    body: str | None
    hashtags: list[str] | None
    char_count: int | None


class CarouselRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    slides: list[dict[str, Any]] | None


class NewsletterStats(BaseModel):
    newsletters_generated: int
    average_generation_time_ms: float
    average_word_count: float
    sections_generated: int
    regenerations_performed: int
    top_sections_regenerated: dict[str, int]
