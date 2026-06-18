"""CollectedArticle model - a normalized ingested article.

``category_id`` links to the (future) classification taxonomy. The
``source_*`` / ``newsletter_section`` / score columns are denormalized hints
captured at collection time from the source strategy.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import ArticleStatus, CollectionMethod, NewsletterSection
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.article_category import ArticleCategory
    from app.models.article_tag import ArticleTag
    from app.models.citation import Citation
    from app.models.content_source import ContentSource
    from app.models.evidence_package import EvidencePackage
    from app.models.fact_check_result import FactCheckResult
    from app.models.verified_claim import VerifiedClaim


class CollectedArticle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "collected_articles"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("article_categories.id", ondelete="SET NULL"),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    raw_content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ArticleStatus] = mapped_column(
        str_enum(ArticleStatus, "article_status"),
        default=ArticleStatus.NEW,
        nullable=False,
        index=True,
    )

    # Collection metadata / strategy hints
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    source_priority: Mapped[int | None] = mapped_column(Integer)
    source_category: Mapped[str | None] = mapped_column(String(120))
    newsletter_section: Mapped[NewsletterSection | None] = mapped_column(
        str_enum(NewsletterSection, "article_newsletter_section", length=64)
    )
    collection_method: Mapped[CollectionMethod | None] = mapped_column(
        str_enum(CollectionMethod, "article_collection_method")
    )
    credibility_score: Mapped[float | None] = mapped_column(Float)
    freshness_score: Mapped[float | None] = mapped_column(Float)
    relevance_hint: Mapped[str | None] = mapped_column(Text)

    # Relevance scoring (0-100 per dimension)
    newsletter_relevance_score: Mapped[float | None] = mapped_column(Float)
    technical_depth_score: Mapped[float | None] = mapped_column(Float)
    enterprise_value_score: Mapped[float | None] = mapped_column(Float)
    qa_value_score: Mapped[float | None] = mapped_column(Float)
    trend_signal_score: Mapped[float | None] = mapped_column(Float)
    overall_relevance_score: Mapped[float | None] = mapped_column(Float, index=True)

    # Deduplication / story grouping
    canonical_story_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)

    # Classification
    primary_category: Mapped[str | None] = mapped_column(String(120))
    secondary_category: Mapped[str | None] = mapped_column(String(120))
    topics: Mapped[list | None] = mapped_column(JSON)
    keywords: Mapped[list | None] = mapped_column(JSON)

    # Ranking / selection
    ranking_position: Mapped[int | None] = mapped_column(Integer, index=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, index=True)

    # Fact-check summary (denormalized for filtering / workflow state)
    verification_status: Mapped[str | None] = mapped_column(String(30), index=True)
    overall_confidence_score: Mapped[float | None] = mapped_column(Float)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped["ContentSource"] = relationship(back_populates="articles", lazy="selectin")
    category: Mapped["ArticleCategory | None"] = relationship(
        back_populates="articles", lazy="selectin"
    )
    tags: Mapped[list["ArticleTag"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )
    verified_claims: Mapped[list["VerifiedClaim"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )
    fact_check_result: Mapped["FactCheckResult | None"] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    evidence_package: Mapped["EvidencePackage | None"] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
