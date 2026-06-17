"""Article query API endpoints (mounted at /api/articles)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.collected_article import CollectedArticle
from app.models.enums import ArticleStatus
from app.schemas.article import ArticleDetail, ArticleRead, ArticleStats
from app.services.stats_service import get_article_stats

router = APIRouter(tags=["articles"])


@router.get("", response_model=list[ArticleRead])
async def list_articles(
    status_filter: ArticleStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[CollectedArticle]:
    stmt = select(CollectedArticle).order_by(CollectedArticle.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(CollectedArticle.status == status_filter)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/stats", response_model=ArticleStats)
async def article_stats(session: AsyncSession = Depends(get_session)) -> ArticleStats:
    return await get_article_stats(session)


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> CollectedArticle:
    article = await session.get(CollectedArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return article
