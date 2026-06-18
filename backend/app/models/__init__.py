"""ORM models package.

Re-exports every model so they register against ``Base.metadata`` on import.
"""

from app.models.agent_run import AgentRun
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.carousel_outline import CarouselOutline
from app.models.citation import Citation
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.evidence_package import EvidencePackage
from app.models.fact_check_result import FactCheckResult
from app.models.feedback_item import FeedbackItem
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.newsletter_section import NewsletterSection
from app.models.newsletter_version import NewsletterVersion
from app.models.publication_analytics import PublicationAnalytics
from app.models.publication_failure import PublicationFailure
from app.models.publication_record import PublicationRecord
from app.models.regeneration_history import RegenerationHistory
from app.models.regeneration_plan import RegenerationPlan
from app.models.review_notification import ReviewNotification
from app.models.review_package import ReviewPackage
from app.models.retry_queue import RetryQueueEntry
from app.models.review_session import ReviewSession
from app.models.review_version import ReviewVersion
from app.models.subscriber import Subscriber
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.verified_claim import VerifiedClaim
from app.models.visual_version import VisualVersion
from app.models.workflow_run import WorkflowRun

__all__ = [
    "AgentRun",
    "ArticleCategory",
    "ArticleTag",
    "CarouselOutline",
    "Citation",
    "CollectedArticle",
    "ContentSource",
    "EvidencePackage",
    "FactCheckResult",
    "FeedbackItem",
    "GeneratedVisual",
    "LinkedInPost",
    "Newsletter",
    "NewsletterDraft",
    "NewsletterSection",
    "NewsletterVersion",
    "PublicationAnalytics",
    "PublicationFailure",
    "PublicationRecord",
    "RegenerationHistory",
    "RegenerationPlan",
    "RetryQueueEntry",
    "ReviewNotification",
    "ReviewPackage",
    "ReviewSession",
    "ReviewVersion",
    "Subscriber",
    "SystemSetting",
    "User",
    "VerifiedClaim",
    "VisualVersion",
    "WorkflowRun",
]
