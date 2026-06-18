"""ReviewVersion model - version history across review/regeneration rounds."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class ReviewVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_versions"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL")
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_summary: Mapped[list | None] = mapped_column(JSON)
    regeneration_plan: Mapped[dict | None] = mapped_column(JSON)
    changed_sections: Mapped[list | None] = mapped_column(JSON)
    reviewer_decision: Mapped[str | None] = mapped_column(String(40))

    newsletter: Mapped["Newsletter"] = relationship(back_populates="review_versions")
