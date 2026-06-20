"""CarouselOutline model - a 10-slide LinkedIn carousel outline."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class CarouselOutline(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "carousel_outlines"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slides: Mapped[list | None] = mapped_column(JSON)

    newsletter: Mapped[Newsletter] = relationship(back_populates="carousel_outlines")
