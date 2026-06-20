"""EvidencePackage model - the publishable evidence bundle for an article."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class EvidencePackage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evidence_packages"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collected_articles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str | None] = mapped_column(String(30))
    supporting_sources: Mapped[list | None] = mapped_column(JSON)
    verification_notes: Mapped[str | None] = mapped_column(Text)
    package: Mapped[dict | None] = mapped_column(JSON)

    article: Mapped[CollectedArticle] = relationship(back_populates="evidence_package")
