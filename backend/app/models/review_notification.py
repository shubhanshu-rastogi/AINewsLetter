"""ReviewNotification model - record of review notifications (email/notion)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.review_session import ReviewSession


class ReviewNotification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_notifications"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(40), default="email")
    status: Mapped[str | None] = mapped_column(String(30), default="prepared")
    payload: Mapped[dict | None] = mapped_column(JSON)

    review_session: Mapped["ReviewSession"] = relationship(back_populates="notifications")
