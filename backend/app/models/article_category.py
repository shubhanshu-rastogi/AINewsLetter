"""ArticleCategory lookup model (seeded)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class ArticleCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "article_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    articles: Mapped[list["CollectedArticle"]] = relationship(
        back_populates="category",
        lazy="selectin",
    )
