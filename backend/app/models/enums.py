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


class VerificationStatus(StrEnum):
    """Fact-check verdict for an article (drives publication eligibility)."""

    VERIFIED = "verified"  # confidence >= 90
    REVIEW_REQUIRED = "review_required"  # 70-89
    LOW_CONFIDENCE = "low_confidence"  # 50-69
    REJECTED = "rejected"  # < 50 (cannot proceed)
    PENDING = "pending"


class ClaimVerification(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class ClaimType(StrEnum):
    FACT = "fact"
    STATISTIC = "statistic"
    METRIC = "metric"
    BENCHMARK = "benchmark"
    PRODUCT_LAUNCH = "product_launch"
    RELEASE = "release"
    EVALUATION = "evaluation"


class TrustTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VisualKind(StrEnum):
    """Specific visual artifact type (finer-grained than VisualType)."""

    COVER = "cover"
    CAROUSEL_SLIDE = "carousel_slide"
    SUMMARY_CARD = "summary_card"
    TOOL_CARD = "tool_card"
    RESEARCH_CARD = "research_card"
    BENCHMARK_CARD = "benchmark_card"
    TAKEAWAY_CARD = "takeaway_card"


class GenerationMethod(StrEnum):
    AI_IMAGE = "ai_image"
    PROGRAMMATIC = "programmatic"


class VisualStatus(StrEnum):
    GENERATED = "generated"
    FAILED = "failed"
    REGENERATED = "regenerated"


class ReviewState(StrEnum):
    """Review session lifecycle (richer than the legacy ReviewStatus enum)."""

    PENDING = "pending"
    FEEDBACK_REQUIRED = "feedback_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ArtifactType(StrEnum):
    NEWSLETTER = "newsletter"
    NEWSLETTER_SECTION = "newsletter_section"
    VISUAL = "visual"
    LINKEDIN_POST = "linkedin_post"
    SOURCE = "source"


class FeedbackCategory(StrEnum):
    CONTENT_CHANGE = "content_change"
    TONE_CHANGE = "tone_change"
    LENGTH_CHANGE = "length_change"
    STRUCTURE_CHANGE = "structure_change"
    VISUAL_CHANGE = "visual_change"
    SOURCE_ISSUE = "source_issue"
    FACT_CHECK_ISSUE = "fact_check_issue"
    APPROVAL_COMMENT = "approval_comment"


class FeedbackSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class PublishState(StrEnum):
    """Per-channel publication state (richer than the legacy PublicationStatus)."""

    DRAFT = "draft"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRYING = "retrying"


class SubscriberStatus(StrEnum):
    ACTIVE = "active"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
