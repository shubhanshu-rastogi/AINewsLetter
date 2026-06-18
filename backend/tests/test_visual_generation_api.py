"""Visual generation API endpoint tests (TestClient + SQLite)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1},
    "executive_summary": "Weekly briefing.",
    "top_stories": [{"headline": "OpenAI ships Agents SDK", "what_happened": "Orchestration."}],
    "tools": [{"name": "Playwright AI", "what_it_does": "Test gen."}],
    "testing": {"title": "LLM-as-judge", "insight": "Rubric judging."},
    "research": {"paper": "Agent tests", "key_findings": "Coverage."},
    "benchmark": {"title": "SWE-bench", "what_improved": "Gains."},
    "trends": [{"signal": "Observability"}],
    "final_takeaways": ["Pilot", "Add gates"],
}


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "VISUAL_STORAGE_ROOT", str(tmp_path / "store"))
    url = f"sqlite+aiosqlite:///{tmp_path / 'visuals_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    ids = {}

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            nl = Newsletter(title="x", issue_number=1)
            s.add(nl)
            await s.flush()
            s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
            await s.commit()
            ids["newsletter_id"] = str(nl.id)

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    import app.api.visuals as visuals_module

    visuals_module.AsyncSessionLocal = sf
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            client.newsletter_id = ids["newsletter_id"]  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_generate_and_read_flow(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]

    gen = api_client.post(f"/api/visuals/generate/{nid}")
    assert gen.status_code == 200
    body = gen.json()
    assert body["carousel_slides"] == 10
    assert body["total"] >= 13

    listing = api_client.get(f"/api/visuals/{nid}")
    assert listing.status_code == 200
    assert len(listing.json()) == body["total"]
    assert listing.json()[0]["preview_url"]

    cover = api_client.get(f"/api/visuals/{nid}/cover")
    assert cover.status_code == 200
    assert cover.json()["width"] == 1200 and cover.json()["height"] == 630

    carousel = api_client.get(f"/api/visuals/{nid}/carousel")
    assert carousel.status_code == 200 and len(carousel.json()) == 10

    metadata = api_client.get(f"/api/visuals/{nid}/metadata")
    assert metadata.status_code == 200
    assert len(metadata.json()["visuals"]) == body["total"]


def test_generate_cover_and_carousel_only(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]

    cover = api_client.post(f"/api/visuals/generate/{nid}/cover")
    assert cover.status_code == 200
    assert cover.json()["visual_kind"] == "cover"

    carousel = api_client.post(f"/api/visuals/generate/{nid}/carousel")
    assert carousel.status_code == 200
    assert carousel.json()["count"] == 10


def test_regenerate_visual(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]
    gen = api_client.post(f"/api/visuals/generate/{nid}")
    visual_id = gen.json()["visual_ids"][0]

    regen = api_client.post(f"/api/visuals/{visual_id}/regenerate")
    assert regen.status_code == 200
    assert regen.json()["version"] == 2

    missing = api_client.post(f"/api/visuals/{uuid.uuid4()}/regenerate")
    assert missing.status_code == 404
