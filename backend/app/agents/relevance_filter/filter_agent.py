"""RelevanceFilterAgent - scores, dedups, ranks, and selects articles."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.relevance_filter import (
    duplicate_detector,
    ranking_engine,
    scoring_engine,
)
from app.agents.relevance_filter.article_selector import SelectionResult, select_articles
from app.agents.relevance_filter.scoring_engine import ScoreBreakdown
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.enums import ArticleStatus

logger = get_logger("relevance")

_SCORE_FIELDS = (
    "credibility_score",
    "freshness_score",
    "newsletter_relevance_score",
    "technical_depth_score",
    "enterprise_value_score",
    "qa_value_score",
    "trend_signal_score",
    "overall_relevance_score",
)


class RelevanceFilterAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    # ----- unit operations ----- #
    def score_article(self, article: CollectedArticle) -> ScoreBreakdown:
        breakdown = scoring_engine.score_article(article)
        for field_name in _SCORE_FIELDS:
            setattr(article, field_name, getattr(breakdown, field_name))
        return breakdown

    def calculate_relevance(self, article: CollectedArticle) -> float:
        return scoring_engine.score_article(article).overall_relevance_score

    def rank_articles(self, articles: Sequence[CollectedArticle]) -> list[CollectedArticle]:
        return ranking_engine.rank_articles(articles)

    def select_articles(self, ranked: Sequence[CollectedArticle]) -> SelectionResult:
        return select_articles(ranked)

    def update_workflow_state(
        self, state: dict[str, Any], selected_ids: list[str], category_map: dict
    ) -> dict[str, Any]:
        return {"selected_article_ids": selected_ids, "category_map": category_map}

    # ----- orchestration ----- #
    async def _load_articles(self, session: AsyncSession, article_ids: Sequence[str] | None) -> list[CollectedArticle]:
        stmt = select(CollectedArticle)
        if article_ids is not None:
            ids = [uuid.UUID(str(a)) for a in article_ids]
            if not ids:
                return []
            stmt = stmt.where(CollectedArticle.id.in_(ids))
        else:
            stmt = stmt.where(CollectedArticle.status == ArticleStatus.NEW)
        return list((await session.execute(stmt)).scalars().all())

    def _score_list(self, articles: Sequence[CollectedArticle]) -> None:
        for article in articles:
            self.score_article(article)
            article.status = ArticleStatus.PROCESSED
        logger.info("scoring_completed", scored=len(articles))

    def _dedup_rank_select(self, articles: Sequence[CollectedArticle]) -> tuple[SelectionResult, int]:
        groups = duplicate_detector.group_stories(articles)
        merged = duplicate_detector.assign_canonical_ids(groups)
        for group in groups:
            for member in group.members:
                if member.id != group.canonical.id:
                    member.status = ArticleStatus.DUPLICATE
        logger.info("duplicates_merged", count=merged)

        ranked = self.rank_articles([g.canonical for g in groups])
        logger.info("articles_ranked", count=len(ranked))

        selection = self.select_articles(ranked)
        logger.info("articles_selected", count=len(selection.selected))
        return selection, merged

    async def score_all(self, article_ids: Sequence[str] | None = None) -> dict[str, Any]:
        """Score the target articles only (no selection)."""
        logger.info("scoring_started")
        async with self.session_factory() as session:
            articles = await self._load_articles(session, article_ids)
            self._score_list(articles)
            await session.commit()
        return {"scored": len(articles)}

    async def select_all(self, article_ids: Sequence[str] | None = None) -> dict[str, Any]:
        """Dedup, rank, and select over already-scored articles."""
        async with self.session_factory() as session:
            stmt = select(CollectedArticle).where(CollectedArticle.status == ArticleStatus.PROCESSED)
            if article_ids is not None:
                ids = [uuid.UUID(str(a)) for a in article_ids]
                stmt = select(CollectedArticle).where(CollectedArticle.id.in_(ids))
            articles = list((await session.execute(stmt)).scalars().all())
            if not articles:
                return {"selected_article_ids": [], "category_map": {}, "duplicates_merged": 0}
            selection, merged = self._dedup_rank_select(articles)
            selected_ids = [str(a.id) for a in selection.selected]
            await session.commit()
        return {
            "selected_article_ids": selected_ids,
            "category_map": selection.category_map,
            "duplicates_merged": merged,
        }

    async def run(self, article_ids: Sequence[str] | None = None) -> dict[str, Any]:
        """Full pipeline: score -> dedup -> rank -> select (used by the node)."""
        logger.info("scoring_started")
        async with self.session_factory() as session:
            articles = await self._load_articles(session, article_ids)
            if not articles:
                logger.info("scoring_completed", scored=0)
                return {
                    "selected_article_ids": [],
                    "category_map": {},
                    "stats": {"scored": 0, "duplicates_merged": 0, "selected": 0},
                }
            self._score_list(articles)
            selection, merged = self._dedup_rank_select(articles)
            selected_ids = [str(a.id) for a in selection.selected]
            await session.commit()

        logger.info("workflow_updated", selected=len(selected_ids))
        return {
            "selected_article_ids": selected_ids,
            "category_map": selection.category_map,
            "stats": {
                "scored": len(articles),
                "duplicates_merged": merged,
                "selected": len(selected_ids),
            },
        }
