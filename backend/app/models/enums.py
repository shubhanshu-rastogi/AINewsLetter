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
    WEBSITE = "website"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    BENCHMARK = "benchmark"
    NEWSLETTER = "newsletter"
    TREND_SIGNAL = "trend_signal"
    ENTERPRISE_REPORT = "enterprise_report"


class ArticleStatus(StrEnum):
    NEW = "new"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class CollectionMethod(StrEnum):
    RSS = "rss"
    WEB = "web"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    NEWSLETTER = "newsletter"


class NewsletterSection(StrEnum):
    AGENTIC_AI_ENGINEERING = "Agentic AI Engineering"
    AI_EVALUATION_QA_GATES = "AI Evaluation & QA Gates"
    AI_TESTING_QUALITY = "AI Testing & Quality Engineering"
    ENTERPRISE_AI_ADOPTION = "Enterprise AI Adoption"
    AI_TOOLS_WATCH = "AI Tools Worth Watching"
    RESEARCH_WATCH = "Research Watch"
    CODING_AGENT_BENCHMARK = "Coding Agent Benchmark Watch"
    WEEKLY_TREND_SIGNALS = "Weekly Trend Signals"


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
