"""PublicationRecord model - a publish attempt to an external channel."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import PublicationChannel, PublicationStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class PublicationRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "publication_records"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel: Mapped[PublicationChannel] = mapped_column(
        str_enum(PublicationChannel, "publication_channel"), nullable=False, index=True
    )
    publication_status: Mapped[PublicationStatus] = mapped_column(
        str_enum(PublicationStatus, "publication_status"),
        default=PublicationStatus.PENDING,
        nullable=False,
        index=True,
    )
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Extended channel state + retry metadata
    publish_state: Mapped[str | None] = mapped_column(String(20), index=True)
    external_publication_id: Mapped[str | None] = mapped_column(String(255))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel_metadata: Mapped[dict | None] = mapped_column(JSON)

    newsletter: Mapped[Newsletter] = relationship(back_populates="publications")
