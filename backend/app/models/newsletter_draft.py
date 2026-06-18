"""NewsletterDraft model - the current assembled content for an issue."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class NewsletterDraft(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_drafts"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    title: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[dict | None] = mapped_column(JSON)  # full newsletter structure
    email_subjects: Mapped[list | None] = mapped_column(JSON)
    word_count: Mapped[int | None] = mapped_column(Integer)
    reading_time_minutes: Mapped[int | None] = mapped_column(Integer)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generation_time_ms: Mapped[float | None] = mapped_column(Float)

    newsletter: Mapped["Newsletter"] = relationship(back_populates="draft")
