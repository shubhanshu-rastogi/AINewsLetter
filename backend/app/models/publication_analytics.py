"""PublicationAnalytics model - per-channel engagement metrics."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class PublicationAnalytics(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "publication_analytics"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    publication_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publication_records.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    open_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    impressions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    engagement: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    growth_metrics: Mapped[dict | None] = mapped_column(JSON)
    is_placeholder: Mapped[bool | None] = mapped_column(Boolean)

    newsletter: Mapped["Newsletter"] = relationship()
