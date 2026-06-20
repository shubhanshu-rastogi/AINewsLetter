"""NewsletterVersion model - immutable content snapshots."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class NewsletterVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_versions"
    __table_args__ = (UniqueConstraint("newsletter_id", "version_number", name="version"),)

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict | None] = mapped_column(JSON)
    word_count: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(255))
    change_reason: Mapped[str | None] = mapped_column(Text)

    newsletter: Mapped[Newsletter] = relationship(back_populates="versions")
