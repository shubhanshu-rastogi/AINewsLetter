"""Content source schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SourceType
from app.schemas.common import ORMModel


class SourceBase(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=255)
    source_type: SourceType
    source_url: str = Field(..., min_length=1, max_length=2048)
    rss_url: str | None = Field(default=None, max_length=2048)
    is_active: bool = True


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: SourceType | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=2048)
    rss_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None


class SourceRead(ORMModel):
    id: uuid.UUID
    source_name: str
    source_type: SourceType
    source_url: str
    rss_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
