"""ORM models package.

Re-exports every model so they register against ``Base.metadata`` on import.
"""

from app.models.agent_run import AgentRun
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.feedback_item import FeedbackItem
from app.models.generated_visual import GeneratedVisual
from app.models.newsletter import Newsletter
from app.models.newsletter_section import NewsletterSection
from app.models.publication_record import PublicationRecord
from app.models.review_session import ReviewSession
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.workflow_run import WorkflowRun

__all__ = [
    "AgentRun",
    "ArticleCategory",
    "ArticleTag",
    "CollectedArticle",
    "ContentSource",
    "FeedbackItem",
    "GeneratedVisual",
    "Newsletter",
    "NewsletterSection",
    "PublicationRecord",
    "ReviewSession",
    "SystemSetting",
    "User",
    "WorkflowRun",
]
