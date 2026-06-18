"""Metadata aggregation module for Alembic.

Importing this module ensures every ORM model is registered against
``Base.metadata`` so that Alembic autogenerate can detect all tables.
"""

from __future__ import annotations

from app.db.base_class import Base  # noqa: F401
from app.models import (  # noqa: F401
    AgentRun,
    ArticleCategory,
    ArticleTag,
    CarouselOutline,
    Citation,
    CollectedArticle,
    ContentSource,
    EvidencePackage,
    FactCheckResult,
    FeedbackItem,
    GeneratedVisual,
    LinkedInPost,
    Newsletter,
    NewsletterDraft,
    NewsletterSection,
    NewsletterVersion,
    PublicationRecord,
    RegenerationHistory,
    ReviewSession,
    SystemSetting,
    User,
    VerifiedClaim,
    WorkflowRun,
)

__all__ = ["Base"]
