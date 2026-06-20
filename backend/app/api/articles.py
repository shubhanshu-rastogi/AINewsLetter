"""Article query + relevance/categorization API endpoints (/api/articles)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.categorization.categorization_agent import CategorizationAgent
from app.agents.relevance_filter.filter_agent import RelevanceFilterAgent
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.collected_article import CollectedArticle
from app.models.enums import ArticleStatus
from app.schemas.article import ArticleDetail, ArticleRead, ArticleStats
from app.services.relevance_stats import (
    get_categories_distribution,
    get_relevance_stats,
    get_trends,
)
from app.services.stats_service import get_article_stats

router = APIRouter(tags=["articles"])


# --- collection-level list/stats --- #
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
    return list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())


@router.get("/stats", response_model=ArticleStats)
async def collection_stats(session: AsyncSession = Depends(get_session)) -> ArticleStats:
    return await get_article_stats(session)


# --- relevance / categorization actions --- #
@router.post("/score")
async def score_articles() -> dict:
    agent = RelevanceFilterAgent(AsyncSessionLocal)
    return await agent.score_all()


@router.post("/categorize")
async def categorize_articles() -> dict:
    agent = CategorizationAgent(AsyncSessionLocal)
    return await agent.run()


@router.post("/select")
async def select_articles() -> dict:
    agent = RelevanceFilterAgent(AsyncSessionLocal)
    return await agent.select_all()


# --- relevance / categorization reads --- #
@router.get("/rankings", response_model=list[ArticleRead])
async def rankings(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[CollectedArticle]:
    stmt = (
        select(CollectedArticle)
        .where(CollectedArticle.ranking_position.is_not(None))
        .order_by(CollectedArticle.ranking_position.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/selected", response_model=list[ArticleRead])
async def selected(session: AsyncSession = Depends(get_session)) -> list[CollectedArticle]:
    stmt = (
        select(CollectedArticle)
        .where(CollectedArticle.is_selected.is_(True))
        .order_by(CollectedArticle.ranking_position.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/categories")
async def categories(session: AsyncSession = Depends(get_session)) -> dict:
    return await get_categories_distribution(session)


@router.get("/trends")
async def trends(session: AsyncSession = Depends(get_session)) -> dict:
    return await get_trends(session)


@router.get("/relevance-stats")
async def relevance_stats(session: AsyncSession = Depends(get_session)) -> dict:
    return await get_relevance_stats(session)


# --- single article (dynamic path last) --- #
@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> CollectedArticle:
    article = await session.get(CollectedArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return article
