"""CategorizationAgent - classifies, tags, and assigns sections to articles."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.categorization import classifier, llm, tagger
from app.agents.categorization.classifier import ClassificationResult
from app.core.config import settings
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection

logger = get_logger("categorization")


class CategorizationAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    # ----- unit operations ----- #
    def classify_article(self, article: CollectedArticle) -> ClassificationResult:
        return classifier.classify(article)

    def generate_tags(self, article: CollectedArticle) -> list[str]:
        return tagger.tags_for(article)

    def assign_newsletter_section(self, article: CollectedArticle) -> NewsletterSection:
        return classifier.classify(article).newsletter_section

    def assign_topics(self, article: CollectedArticle) -> list[str]:
        return tagger.topics_for(article)

    def update_database(self, article: CollectedArticle, result: ClassificationResult) -> None:
        article.primary_category = result.primary_category
        article.secondary_category = result.secondary_category
        article.newsletter_section = result.newsletter_section
        article.topics = result.topics
        article.keywords = result.keywords

    # ----- orchestration ----- #
    async def _load_articles(self, session: AsyncSession, article_ids: Sequence[str] | None) -> list[CollectedArticle]:
        stmt = select(CollectedArticle)
        if article_ids is not None:
            ids = [uuid.UUID(str(a)) for a in article_ids]
            if not ids:
                return []
            stmt = stmt.where(CollectedArticle.id.in_(ids))
        else:
            stmt = stmt.where(CollectedArticle.is_selected.is_(True))
        return list((await session.execute(stmt)).scalars().all())

    async def run(self, article_ids: Sequence[str] | None = None) -> dict[str, Any]:
        logger.info("classification_started")
        async with self.session_factory() as session:
            articles = await self._load_articles(session, article_ids)
            category_map: dict[str, list[str]] = {}

            for article in articles:
                result = self.classify_article(article)
                if settings.ENABLE_LLM_CLASSIFICATION:
                    enrichment = await llm.llm_classify(article)
                    if enrichment:
                        result.keywords = sorted(set(result.keywords) | set(enrichment.get("keywords", [])))
                        result.topics = sorted(set(result.topics) | set(enrichment.get("topics", [])))
                self.update_database(article, result)
                section = result.newsletter_section.value
                category_map.setdefault(section, []).append(str(article.id))

            await session.commit()

        logger.info("classification_completed", classified=len(articles))
        return {"category_map": category_map, "classified": len(articles)}
