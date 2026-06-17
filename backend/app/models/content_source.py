"""ContentSource model - where articles are collected from."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import SourceType
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.collected_article import CollectedArticle


class ContentSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_sources"

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        str_enum(SourceType, "source_type"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    rss_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    articles: Mapped[list["CollectedArticle"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
