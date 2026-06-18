"""Relevance / categorization API endpoint tests (TestClient + SQLite)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.db.base import Base
from app.main import app
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod, NewsletterSection, SourceType


@pytest.fixture
def api_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'rel_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = datetime.now(timezone.utc)
        async with sf() as s:
            src = ContentSource(
                source_name="Docs", source_type=SourceType.DOCUMENTATION,
                source_url="https://ex.com", priority=1, credibility_score=0.95,
                freshness_score=0.8, relevance_score=0.9,
                preferred_collection_method=CollectionMethod.DOCUMENTATION,
                category="Agentic AI Engineering",
            )
            s.add(src)
            await s.flush()
            for i in range(4):
                s.add(CollectedArticle(
                    source_id=src.id,
                    title=f"AI agent orchestration and evaluation guide {i}",
                    url=f"https://ex.com/a{i}",
                    raw_content="agents orchestration architecture evaluation enterprise testing " * 8,
                    status=ArticleStatus.NEW,
                    credibility_score=0.95,
                    published_date=now,
                    source_category="Agentic AI Engineering",
                    newsletter_section=NewsletterSection.AGENTIC_AI_ENGINEERING,
                ))
            await s.commit()

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    import app.api.articles as articles_module

    articles_module.AsyncSessionLocal = sf  # agent uses this in the action endpoints
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_score_select_categorize_flow(api_client: TestClient) -> None:
    score = api_client.post("/api/articles/score")
    assert score.status_code == 200
    assert score.json()["scored"] == 4

    select = api_client.post("/api/articles/select")
    assert select.status_code == 200
    assert len(select.json()["selected_article_ids"]) >= 1

    categorize = api_client.post("/api/articles/categorize")
    assert categorize.status_code == 200
    assert categorize.json()["classified"] >= 1

    rankings = api_client.get("/api/articles/rankings")
    assert rankings.status_code == 200
    body = rankings.json()
    assert body and body[0]["ranking_position"] == 1
    assert body[0]["overall_relevance_score"] is not None

    selected = api_client.get("/api/articles/selected")
    assert selected.status_code == 200
    assert len(selected.json()) >= 1
    assert selected.json()[0]["is_selected"] is True


def test_categories_trends_stats(api_client: TestClient) -> None:
    api_client.post("/api/articles/score")
    api_client.post("/api/articles/select")
    api_client.post("/api/articles/categorize")

    cats = api_client.get("/api/articles/categories")
    assert cats.status_code == 200
    assert "by_section" in cats.json()

    trends = api_client.get("/api/articles/trends")
    assert trends.status_code == 200
    assert "top_keywords" in trends.json()

    stats = api_client.get("/api/articles/relevance-stats")
    assert stats.status_code == 200
    sbody = stats.json()
    assert sbody["total_articles"] == 4
    assert sbody["articles_scored"] == 4
    assert sbody["articles_selected"] >= 1
    assert sbody["average_relevance_score"] > 0
