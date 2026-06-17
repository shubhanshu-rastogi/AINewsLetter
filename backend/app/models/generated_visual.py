"""GeneratedVisual model - an image/asset attached to a newsletter."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import VisualType
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter


class GeneratedVisual(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "generated_visuals"

    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    visual_type: Mapped[VisualType] = mapped_column(
        str_enum(VisualType, "visual_type"), nullable=False
    )
    prompt_used: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(2048))

    newsletter: Mapped["Newsletter"] = relationship(back_populates="visuals")
