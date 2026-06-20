"""ReviewPackage model - the review-ready snapshot shown to a human reviewer."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.review_session import ReviewSession


class ReviewPackage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_packages"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package: Mapped[dict | None] = mapped_column(JSON)

    review_session: Mapped[ReviewSession] = relationship(back_populates="package")
