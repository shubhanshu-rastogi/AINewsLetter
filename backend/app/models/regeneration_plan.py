"""RegenerationPlan model - the targeted regeneration plan for a review round."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.review_session import ReviewSession


class RegenerationPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "regeneration_plans"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[dict | None] = mapped_column(JSON)
    executed: Mapped[bool | None] = mapped_column(Boolean)

    review_session: Mapped[ReviewSession] = relationship(back_populates="regeneration_plans")
