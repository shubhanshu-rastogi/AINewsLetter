"""Citation model - a traceable source reference for an article."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class Citation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "citations"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collected_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieval_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    article: Mapped[CollectedArticle] = relationship(back_populates="citations")
