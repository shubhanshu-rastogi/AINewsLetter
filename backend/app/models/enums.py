"""Enumerations used across models, schemas, and validation.

All enums are ``str``-based (``StrEnum``) so their values serialize cleanly to
JSON and are stored as readable strings in the database. They are the single
source of truth for allowed values at both the API and persistence layers.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class SourceType(StrEnum):
    RSS = "rss"
    BLOG = "blog"
    NEWS = "news"
    GITHUB = "github"
    PAPER = "paper"
    REPORT = "report"


class ArticleStatus(StrEnum):
    NEW = "new"
    FILTERED = "filtered"
    RELEVANT = "relevant"
    CATEGORIZED = "categorized"
    REJECTED = "rejected"
    USED = "used"


class NewsletterStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VisualType(StrEnum):
    HERO = "hero"
    SECTION = "section"
    SOCIAL = "social"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class FeedbackType(StrEnum):
    REWRITE = "rewrite"
    TONE = "tone"
    FACTUAL = "factual"
    CUT = "cut"
    ADD = "add"
    GENERAL = "general"


class ResolutionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class PublicationChannel(StrEnum):
    BEEHIIV = "beehiiv"
    LINKEDIN = "linkedin"
    EMAIL = "email"


class PublicationStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class ExecutionStatus(StrEnum):
    """Shared status for agent_runs and workflow_runs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
