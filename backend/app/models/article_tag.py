"""ArticleTag model - free-form tags attached to an article."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class ArticleTag(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "article_tags"
    __table_args__ = (
        UniqueConstraint("article_id", "tag_name", name="article_tag"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collected_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)

    article: Mapped["CollectedArticle"] = relationship(back_populates="tags")
