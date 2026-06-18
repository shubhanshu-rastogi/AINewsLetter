"""Article, tag, and category schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ArticleStatus, CollectionMethod, NewsletterSection
from app.schemas.common import ORMModel


# --- Category ---
class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None


# --- Tag ---
class TagRead(ORMModel):
    id: uuid.UUID
    article_id: uuid.UUID
    tag_name: str


# --- Article ---
class ArticleRead(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    title: str
    url: str
    author: str | None
    published_date: datetime | None
    summary: str | None
    status: ArticleStatus
    content_hash: str | None
    source_priority: int | None
    source_category: str | None
    newsletter_section: NewsletterSection | None
    collection_method: CollectionMethod | None
    credibility_score: float | None
    freshness_score: float | None
    # Relevance / classification
    overall_relevance_score: float | None
    ranking_position: int | None
    is_selected: bool | None
    primary_category: str | None
    secondary_category: str | None
    topics: list[str] | None
    keywords: list[str] | None
    canonical_story_id: uuid.UUID | None
    created_at: datetime


class ArticleDetail(ArticleRead):
    raw_content: str | None
    relevance_hint: str | None
    newsletter_relevance_score: float | None
    technical_depth_score: float | None
    enterprise_value_score: float | None
    qa_value_score: float | None
    trend_signal_score: float | None


# --- Statistics ---
class ArticleStats(BaseModel):
    total_sources: int
    active_sources: int
    total_articles: int
    duplicates: int
    failed_collections: int
    last_collection_time: str | None = None
    articles_by_category: dict[str, int] = Field(default_factory=dict)
    articles_by_newsletter_section: dict[str, int] = Field(default_factory=dict)
    articles_by_source_priority: dict[str, int] = Field(default_factory=dict)
