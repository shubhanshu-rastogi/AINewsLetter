"""Repository layer."""

from app.repositories.article_repository import ArticleRepository
from app.repositories.base import BaseRepository, Page
from app.repositories.newsletter_repository import NewsletterRepository
from app.repositories.publication_repository import PublicationRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "Page",
    "ArticleRepository",
    "NewsletterRepository",
    "PublicationRepository",
    "ReviewRepository",
    "SourceRepository",
    "UserRepository",
]
