"""Newsletter model - a single newsletter issue."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import NewsletterStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.carousel_outline import CarouselOutline
    from app.models.generated_visual import GeneratedVisual
    from app.models.linkedin_post import LinkedInPost
    from app.models.newsletter_draft import NewsletterDraft
    from app.models.newsletter_section import NewsletterSection
    from app.models.newsletter_version import NewsletterVersion
    from app.models.publication_record import PublicationRecord
    from app.models.regeneration_history import RegenerationHistory
    from app.models.review_session import ReviewSession
    from app.models.review_version import ReviewVersion
    from app.models.workflow_run import WorkflowRun


class Newsletter(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "newsletters"

    title: Mapped[str | None] = mapped_column(String(512))
    issue_number: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[NewsletterStatus] = mapped_column(
        str_enum(NewsletterStatus, "newsletter_status"),
        default=NewsletterStatus.DRAFT,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    sections: Mapped[list["NewsletterSection"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    visuals: Mapped[list["GeneratedVisual"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    review_sessions: Mapped[list["ReviewSession"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    publications: Mapped[list["PublicationRecord"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="newsletter", lazy="selectin"
    )
    draft: Mapped["NewsletterDraft | None"] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    versions: Mapped[list["NewsletterVersion"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    linkedin_posts: Mapped[list["LinkedInPost"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    carousel_outlines: Mapped[list["CarouselOutline"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    regeneration_history: Mapped[list["RegenerationHistory"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
    review_versions: Mapped[list["ReviewVersion"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan", lazy="selectin"
    )
