"""Content source schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CollectionMethod, NewsletterSection, SourceType
from app.schemas.common import ORMModel


class SourceBase(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=255)
    source_type: SourceType
    source_url: str = Field(..., min_length=1, max_length=2048)
    rss_url: str | None = Field(default=None, max_length=2048)
    category: str | None = Field(default=None, max_length=120)
    best_use: str | None = None
    is_active: bool = True
    priority: int = Field(default=100, ge=1)
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_collection_method: CollectionMethod = CollectionMethod.WEB
    fallback_collection_method: CollectionMethod | None = None
    newsletter_section: NewsletterSection | None = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: SourceType | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=2048)
    rss_url: str | None = Field(default=None, max_length=2048)
    category: str | None = Field(default=None, max_length=120)
    best_use: str | None = None
    is_active: bool | None = None
    priority: int | None = Field(default=None, ge=1)
    credibility_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    preferred_collection_method: CollectionMethod | None = None
    fallback_collection_method: CollectionMethod | None = None
    newsletter_section: NewsletterSection | None = None


class SourceRead(ORMModel):
    id: uuid.UUID
    source_name: str
    source_type: SourceType
    source_url: str
    rss_url: str | None
    category: str | None
    best_use: str | None
    is_active: bool
    priority: int
    credibility_score: float
    freshness_score: float
    relevance_score: float
    preferred_collection_method: CollectionMethod
    fallback_collection_method: CollectionMethod | None
    newsletter_section: NewsletterSection | None
    created_at: datetime
    updated_at: datetime


class SourceStrategyView(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    category: str | None
    priority: int
    credibility_score: float
    freshness_score: float
    relevance_score: float
    composite_score: float
    preferred_collection_method: CollectionMethod
    fallback_collection_method: CollectionMethod | None
    newsletter_section: NewsletterSection | None
