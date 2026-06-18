"""ReviewSession model - a human editorial review of a newsletter."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import ReviewState, ReviewStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem
    from app.models.newsletter import Newsletter
    from app.models.regeneration_plan import RegenerationPlan
    from app.models.review_notification import ReviewNotification
    from app.models.review_package import ReviewPackage


class ReviewSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_sessions"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ``reviewer`` is kept as a free-text field per the spec. See the schema
    # review notes: promoting this to a FK on ``users.id`` is recommended.
    reviewer: Mapped[str | None] = mapped_column(String(255))
    review_status: Mapped[ReviewStatus] = mapped_column(
        str_enum(ReviewStatus, "review_status"),
        default=ReviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    comments: Mapped[str | None] = mapped_column(Text)

    # Extended review lifecycle (richer than the legacy review_status enum)
    review_state: Mapped[str] = mapped_column(
        String(30), default=ReviewState.PENDING.value, nullable=False, index=True
    )
    notion_page_url: Mapped[str | None] = mapped_column(String(2048))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_number: Mapped[int | None] = mapped_column(Integer)

    newsletter: Mapped["Newsletter"] = relationship(back_populates="review_sessions")
    feedback_items: Mapped[list["FeedbackItem"]] = relationship(
        back_populates="review_session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    package: Mapped["ReviewPackage | None"] = relationship(
        back_populates="review_session", cascade="all, delete-orphan",
        uselist=False, lazy="selectin",
    )
    regeneration_plans: Mapped[list["RegenerationPlan"]] = relationship(
        back_populates="review_session", cascade="all, delete-orphan", lazy="selectin"
    )
    notifications: Mapped[list["ReviewNotification"]] = relationship(
        back_populates="review_session", cascade="all, delete-orphan", lazy="selectin"
    )
