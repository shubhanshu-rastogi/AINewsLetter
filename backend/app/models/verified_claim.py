"""VerifiedClaim model - an extracted factual claim and its verdict."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class VerifiedClaim(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "verified_claims"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collected_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str | None] = mapped_column(String(40))
    verification_status: Mapped[str | None] = mapped_column(String(30), index=True)
    support_score: Mapped[float | None] = mapped_column(Float)
    corroborating_sources: Mapped[int | None] = mapped_column(Float)

    article: Mapped["CollectedArticle"] = relationship(back_populates="verified_claims")
