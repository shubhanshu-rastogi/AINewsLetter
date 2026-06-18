"""GeneratedVisual model - an image/asset attached to a newsletter.

``visual_type`` keeps the coarse legacy enum (hero/section/social); ``visual_kind``
is the finer-grained artifact type (cover, carousel_slide, *_card). Both are set
so existing consumers keep working while new code uses ``visual_kind``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import VisualType
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.newsletter import Newsletter
    from app.models.visual_version import VisualVersion


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

    # Extended metadata
    visual_kind: Mapped[str | None] = mapped_column(String(50), index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    generation_method: Mapped[str | None] = mapped_column(String(30))
    file_format: Mapped[str | None] = mapped_column(String(10))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    status: Mapped[str | None] = mapped_column(String(30))

    newsletter: Mapped["Newsletter"] = relationship(back_populates="visuals")
    versions: Mapped[list["VisualVersion"]] = relationship(
        back_populates="visual", cascade="all, delete-orphan", lazy="selectin"
    )
