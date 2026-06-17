"""NewsletterSection model - a single block within an issue."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class NewsletterSection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_sections"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    section_name: Mapped[str | None] = mapped_column(String(255))
    section_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    newsletter: Mapped["Newsletter"] = relationship(back_populates="sections")
