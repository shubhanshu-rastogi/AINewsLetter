"""Newsletter, section, and visual schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import NewsletterStatus, VisualType
from app.schemas.common import ORMModel


# --- Section ---
class SectionBase(BaseModel):
    section_name: str | None = Field(default=None, max_length=255)
    section_order: int = Field(default=0, ge=0)
    content: str | None = None
    word_count: int = Field(default=0, ge=0)


class SectionCreate(SectionBase):
    newsletter_id: uuid.UUID


class SectionRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    section_name: str | None
    section_order: int
    content: str | None
    word_count: int


# --- Visual ---
class VisualCreate(BaseModel):
    newsletter_id: uuid.UUID
    visual_type: VisualType
    prompt_used: str | None = None
    file_path: str | None = Field(default=None, max_length=2048)


class VisualRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    visual_type: VisualType
    prompt_used: str | None
    file_path: str | None
    created_at: datetime


# --- Newsletter ---
class NewsletterBase(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    issue_number: int | None = Field(default=None, ge=1)
    publication_date: datetime | None = None
    status: NewsletterStatus = NewsletterStatus.DRAFT
    version: int = Field(default=1, ge=1)


class NewsletterCreate(NewsletterBase):
    pass


class NewsletterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    issue_number: int | None = Field(default=None, ge=1)
    publication_date: datetime | None = None
    status: NewsletterStatus | None = None
    version: int | None = Field(default=None, ge=1)


class NewsletterRead(ORMModel):
    id: uuid.UUID
    title: str | None
    issue_number: int | None
    publication_date: datetime | None
    status: NewsletterStatus
    version: int
    created_at: datetime
    updated_at: datetime


class NewsletterDetail(NewsletterRead):
    sections: list[SectionRead] = []
