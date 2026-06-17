"""Collection API endpoint tests (TestClient, mocked collectors)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.db.base import Base
from app.main import app

RSS_XML = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>API Article</title><link>https://ex.com/api-1</link>
<description>snip</description></item></channel></rss>"""

HTML_PAGE = "<html><head><title>Page</title></head><body><article>Body</article></body></html>"


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path / 'collect_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Mock all external fetches so /collect works offline.
    async def fake_bytes(url, **kw):
        return RSS_XML

    async def fake_text(url, **kw):
        return HTML_PAGE

    async def allow(url):
        return True

    from app.agents.source_collection import (
        documentation_collector,
        research_collector,
        rss_collector,
        web_collector,
    )

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_bytes)
    monkeypatch.setattr(research_collector, "fetch_bytes", fake_bytes)
    monkeypatch.setattr(web_collector, "fetch_text", fake_text)
    monkeypatch.setattr(web_collector, "is_allowed_by_robots", allow)
    monkeypatch.setattr(documentation_collector, "fetch_text", fake_text)
    monkeypatch.setattr(documentation_collector, "is_allowed_by_robots", allow)
    # The collect endpoint constructs the agent with AsyncSessionLocal.
    monkeypatch.setattr("app.api.sources.AsyncSessionLocal", sf)

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_seed_and_strategy_and_collect(api_client: TestClient) -> None:
    # Seed the 15 curated sources.
    seed = api_client.post("/api/sources/seed")
    assert seed.status_code == 200
    assert seed.json()["created"] == 15

    # Re-seeding is idempotent.
    assert api_client.post("/api/sources/seed").json()["created"] == 0

    sources = api_client.get("/api/sources")
    assert sources.status_code == 200
    assert len(sources.json()) == 15

    strategy = api_client.get("/api/sources/strategy")
    assert strategy.status_code == 200
    body = strategy.json()
    assert len(body) == 15
    assert "composite_score" in body[0]
    assert body[0]["priority"] <= body[-1]["priority"]  # ordered by priority

    # Manual collection across all sources.
    collect = api_client.post("/api/sources/collect")
    assert collect.status_code == 200
    assert collect.json()["new_articles"] >= 1

    # Articles + stats.
    articles = api_client.get("/api/articles")
    assert articles.status_code == 200
    assert len(articles.json()) >= 1

    stats = api_client.get("/api/articles/stats")
    assert stats.status_code == 200
    sbody = stats.json()
    assert sbody["total_sources"] == 15
    assert sbody["active_sources"] == 15
    assert sbody["total_articles"] >= 1
    assert sbody["last_collection_time"] is not None


def test_source_crud(api_client: TestClient) -> None:
    payload = {
        "source_name": "Custom",
        "source_type": "rss",
        "source_url": "https://custom.example.com",
        "rss_url": "https://custom.example.com/feed",
        "category": "Agentic AI Engineering",
        "priority": 5,
    }
    created = api_client.post("/api/sources", json=payload)
    assert created.status_code == 201
    source_id = created.json()["id"]

    fetched = api_client.get(f"/api/sources/{source_id}")
    assert fetched.status_code == 200
    assert fetched.json()["source_name"] == "Custom"

    updated = api_client.put(f"/api/sources/{source_id}", json={"is_active": False})
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = api_client.delete(f"/api/sources/{source_id}")
    assert deleted.status_code == 204
    assert api_client.get(f"/api/sources/{source_id}").status_code == 404
