"""VisualVersion model - history of regenerated visual assets."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.generated_visual import GeneratedVisual


class VisualVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "visual_versions"

    visual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generated_visuals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(2048))
    prompt_used: Mapped[str | None] = mapped_column(Text)
    change_reason: Mapped[str | None] = mapped_column(Text)

    visual: Mapped["GeneratedVisual"] = relationship(back_populates="versions")
