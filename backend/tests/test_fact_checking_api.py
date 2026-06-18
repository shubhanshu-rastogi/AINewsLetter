"""Fact-checking API endpoint tests (TestClient + SQLite)."""

from __future__ import annotations

import asyncio
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
from app.models.enums import ArticleStatus, CollectionMethod, SourceType


@pytest.fixture
def api_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'facts_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    article_id = {}

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            src = ContentSource(
                source_name="Docs", source_type=SourceType.DOCUMENTATION,
                source_url="https://ex.com", priority=1, credibility_score=0.9,
                freshness_score=0.8, relevance_score=0.9,
                preferred_collection_method=CollectionMethod.DOCUMENTATION,
                category="Agentic AI Engineering",
            )
            s.add(src)
            await s.flush()
            art = CollectedArticle(
                source_id=src.id,
                title="Agent orchestration framework launch",
                url="https://ex.com/story",
                raw_content="The agent achieves 95% accuracy on SWE-bench. "
                            "OpenAI launches a new orchestration framework today.",
                summary="Agent orchestration framework.",
                status=ArticleStatus.PROCESSED, is_selected=True,
                published_date=datetime.now(timezone.utc),
                source_category="Agentic AI Engineering",
            )
            s.add(art)
            await s.commit()
            article_id["id"] = str(art.id)

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    import app.api.facts as facts_module

    facts_module.AsyncSessionLocal = sf
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            client.article_id = article_id["id"]  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_verify_and_read_flow(api_client: TestClient) -> None:
    aid = api_client.article_id  # type: ignore[attr-defined]

    verify = api_client.post("/api/facts/verify")
    assert verify.status_code == 200
    assert len(verify.json()["fact_check_results"]) == 1

    results = api_client.get("/api/facts/results")
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["overall_confidence_score"] is not None

    one = api_client.get(f"/api/facts/results/{aid}")
    assert one.status_code == 200
    assert one.json()["verification_status"]

    evidence = api_client.get(f"/api/facts/evidence/{aid}")
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["package"]["article_id"] == aid
    assert "claims" in body["package"]

    citations = api_client.get(f"/api/facts/citations/{aid}")
    assert citations.status_code == 200
    assert len(citations.json()) >= 1
    assert citations.json()[0]["retrieval_timestamp"] is not None

    stats = api_client.get("/api/facts/statistics")
    assert stats.status_code == 200
    sbody = stats.json()
    assert sbody["citations_created"] >= 1
    assert sbody["claims_extracted"] >= 1
    assert sbody["average_confidence_score"] > 0


def test_verify_single_article(api_client: TestClient) -> None:
    aid = api_client.article_id  # type: ignore[attr-defined]
    resp = api_client.post(f"/api/facts/verify/{aid}")
    assert resp.status_code == 200
    assert len(resp.json()["fact_check_results"]) == 1


def test_missing_result_404(api_client: TestClient) -> None:
    import uuid

    resp = api_client.get(f"/api/facts/results/{uuid.uuid4()}")
    assert resp.status_code == 404
