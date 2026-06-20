"""Relevance / categorization statistics + aggregations."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_article import CollectedArticle
from app.models.enums import ArticleStatus


async def _group_counts(session: AsyncSession, column) -> dict[str, int]:
    rows = await session.execute(select(column, func.count()).group_by(column))
    return {str(k) if k is not None else "uncategorized": c for k, c in rows}


async def _flatten_json_counter(session: AsyncSession, column, top: int) -> dict[str, int]:
    rows = await session.execute(select(column).where(column.is_not(None)))
    counter: Counter[str] = Counter()
    for (values,) in rows:
        if isinstance(values, list):
            counter.update(str(v) for v in values)
    return dict(counter.most_common(top))


async def get_relevance_stats(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count()).select_from(CollectedArticle))
    scored = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(CollectedArticle.overall_relevance_score.is_not(None))
    )
    duplicates = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(CollectedArticle.status == ArticleStatus.DUPLICATE)
    )
    selected = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(CollectedArticle.is_selected.is_(True))
    )
    avg_score = await session.scalar(select(func.avg(CollectedArticle.overall_relevance_score)))

    top_sources_rows = await session.execute(
        select(CollectedArticle.source_category, func.count())
        .group_by(CollectedArticle.source_category)
        .order_by(func.count().desc())
        .limit(10)
    )

    return {
        "total_articles": int(total or 0),
        "articles_scored": int(scored or 0),
        "duplicates_merged": int(duplicates or 0),
        "articles_selected": int(selected or 0),
        "articles_by_section": await _group_counts(session, CollectedArticle.newsletter_section),
        "average_relevance_score": round(float(avg_score), 2) if avg_score else 0.0,
        "top_keywords": await _flatten_json_counter(session, CollectedArticle.keywords, 15),
        "top_topics": await _flatten_json_counter(session, CollectedArticle.topics, 15),
        "top_sources": {(k or "uncategorized"): c for k, c in top_sources_rows},
    }


async def get_categories_distribution(session: AsyncSession) -> dict:
    return {
        "by_section": await _group_counts(session, CollectedArticle.newsletter_section),
        "by_primary_category": await _group_counts(session, CollectedArticle.primary_category),
    }


async def get_trends(session: AsyncSession) -> dict:
    rows = await session.execute(
        select(CollectedArticle)
        .where(CollectedArticle.trend_signal_score.is_not(None))
        .order_by(CollectedArticle.trend_signal_score.desc())
        .limit(10)
    )
    top_trending = [
        {
            "id": str(a.id),
            "title": a.title,
            "trend_signal_score": a.trend_signal_score,
            "newsletter_section": a.newsletter_section,
        }
        for a in rows.scalars().all()
    ]
    return {
        "top_keywords": await _flatten_json_counter(session, CollectedArticle.keywords, 15),
        "top_topics": await _flatten_json_counter(session, CollectedArticle.topics, 15),
        "top_trending": top_trending,
    }
