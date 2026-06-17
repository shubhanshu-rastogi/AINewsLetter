"""ContentSource model - where articles are collected from."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import CollectionMethod, NewsletterSection, SourceType
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class ContentSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_sources"

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        str_enum(SourceType, "source_type"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    rss_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Editorial metadata
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    best_use: Mapped[str | None] = mapped_column(Text)

    # Source strategy (priority + scoring + routing)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    preferred_collection_method: Mapped[CollectionMethod] = mapped_column(
        str_enum(CollectionMethod, "preferred_collection_method"),
        default=CollectionMethod.WEB,
        nullable=False,
    )
    fallback_collection_method: Mapped[CollectionMethod | None] = mapped_column(
        str_enum(CollectionMethod, "fallback_collection_method")
    )
    newsletter_section: Mapped[NewsletterSection | None] = mapped_column(
        str_enum(NewsletterSection, "source_newsletter_section", length=64)
    )

    articles: Mapped[list["CollectedArticle"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
