"""FeedbackItem model - one actionable item within a review session."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import FeedbackType, ResolutionStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.review_session import ReviewSession


class FeedbackItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "feedback_items"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    feedback_type: Mapped[FeedbackType] = mapped_column(
        str_enum(FeedbackType, "feedback_type"),
        default=FeedbackType.GENERAL,
        nullable=False,
    )
    feedback_text: Mapped[str | None] = mapped_column(Text)
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        str_enum(ResolutionStatus, "resolution_status"),
        default=ResolutionStatus.OPEN,
        nullable=False,
        index=True,
    )

    review_session: Mapped["ReviewSession"] = relationship(back_populates="feedback_items")
