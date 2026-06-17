"""Collection statistics service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.source_collection.collector import LAST_RUN_SETTING_KEY
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus
from app.models.system_setting import SystemSetting
from app.schemas.article import ArticleStats


async def _group_counts(session: AsyncSession, column) -> dict[str, int]:
    rows = await session.execute(
        select(column, func.count()).group_by(column)
    )
    return {str(key) if key is not None else "uncategorized": count for key, count in rows}


async def get_article_stats(session: AsyncSession) -> ArticleStats:
    total_sources = await session.scalar(select(func.count()).select_from(ContentSource))
    active_sources = await session.scalar(
        select(func.count()).select_from(ContentSource).where(
            ContentSource.is_active.is_(True)
        )
    )
    total_articles = await session.scalar(
        select(func.count()).select_from(CollectedArticle)
    )
    duplicates = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(
            CollectedArticle.status == ArticleStatus.DUPLICATE
        )
    )
    failed = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(
            CollectedArticle.status == ArticleStatus.FAILED
        )
    )
    last_run = await session.scalar(
        select(SystemSetting.value).where(SystemSetting.key == LAST_RUN_SETTING_KEY)
    )

    return ArticleStats(
        total_sources=int(total_sources or 0),
        active_sources=int(active_sources or 0),
        total_articles=int(total_articles or 0),
        duplicates=int(duplicates or 0),
        failed_collections=int(failed or 0),
        last_collection_time=last_run,
        articles_by_category=await _group_counts(session, CollectedArticle.source_category),
        articles_by_newsletter_section=await _group_counts(
            session, CollectedArticle.newsletter_section
        ),
        articles_by_source_priority=await _group_counts(
            session, CollectedArticle.source_priority
        ),
    )
