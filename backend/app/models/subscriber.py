"""Subscriber model - newsletter audience member."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import SubscriberStatus
from app.models.mixins import TimestampMixin, UUIDMixin


class Subscriber(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscribers"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[SubscriberStatus] = mapped_column(
        str_enum(SubscriberStatus, "subscriber_status"),
        default=SubscriberStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(80))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
