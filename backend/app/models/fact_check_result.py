"""FactCheckResult model - per-article confidence breakdown + verdict."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class FactCheckResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_check_results"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collected_articles.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    url_accessible: Mapped[bool | None] = mapped_column(Boolean)
    source_credibility_score: Mapped[float | None] = mapped_column(Float)
    claim_verification_score: Mapped[float | None] = mapped_column(Float)
    cross_source_score: Mapped[float | None] = mapped_column(Float)
    freshness_score: Mapped[float | None] = mapped_column(Float)
    evidence_score: Mapped[float | None] = mapped_column(Float)
    overall_confidence_score: Mapped[float | None] = mapped_column(Float, index=True)
    verification_status: Mapped[str | None] = mapped_column(String(30), index=True)
    fact_check_notes: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    article: Mapped["CollectedArticle"] = relationship(back_populates="fact_check_result")
