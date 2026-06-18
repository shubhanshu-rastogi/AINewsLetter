"""LinkedInPost model - generated LinkedIn announcement content."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class LinkedInPost(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "linkedin_posts"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant: Mapped[str | None] = mapped_column(String(50), default="announcement")
    body: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list | None] = mapped_column(JSON)
    char_count: Mapped[int | None] = mapped_column(Integer)

    newsletter: Mapped["Newsletter"] = relationship(back_populates="linkedin_posts")
