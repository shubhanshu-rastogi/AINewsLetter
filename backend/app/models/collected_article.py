"""CollectedArticle model - a normalized ingested article.

Note: ``category_id`` is an added nullable FK (not in the bare field list) so
categorization has a concrete one-to-many link (category -> articles). It is
nullable because an article is uncategorized when first collected.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import ArticleStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.article_category import ArticleCategory
    from app.models.article_tag import ArticleTag
    from app.models.content_source import ContentSource


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

    source: Mapped["ContentSource"] = relationship(back_populates="articles", lazy="selectin")
    category: Mapped["ArticleCategory | None"] = relationship(
        back_populates="articles", lazy="selectin"
    )
    tags: Mapped[list["ArticleTag"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
