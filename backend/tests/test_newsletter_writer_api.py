"""Newsletter writer API endpoint tests (TestClient + SQLite)."""

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
from app.models.enums import ArticleStatus, CollectionMethod
from app.models.enums import NewsletterSection as NS
from app.models.enums import SourceType, VerificationStatus

SAMPLES = [
    ("OpenAI ships Agents SDK", "Orchestration, guardrails, tracing.", NS.AGENTIC_AI_ENGINEERING),
    ("Playwright AI test gen", "Generate tests from natural language.", NS.AI_TOOLS_WATCH),
    ("LLM-as-judge matures", "Rubric judging + CI gates.", NS.AI_TESTING_QUALITY),
    ("Enterprise agentic rollout", "Governance + measured ROI.", NS.ENTERPRISE_AI_ADOPTION),
    ("Agent-authored tests paper", "Agents author maintainable tests.", NS.RESEARCH_WATCH),
    ("SWE-bench new high", "Coding agents improve; gaps remain.", NS.CODING_AGENT_BENCHMARK),
    ("Observability trend", "Tracing and eval pipelines trend.", NS.WEEKLY_TREND_SIGNALS),
]


@pytest.fixture
def api_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'writer_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            src = ContentSource(
                source_name="OpenAI", source_type=SourceType.DOCUMENTATION,
                source_url="https://openai.com", priority=1, credibility_score=0.95,
                freshness_score=0.9, relevance_score=0.9,
                preferred_collection_method=CollectionMethod.DOCUMENTATION, category="AI",
            )
            s.add(src)
            await s.flush()
            for title, content, section in SAMPLES:
                s.add(CollectedArticle(
                    source_id=src.id, title=title, url=f"https://openai.com/{uuid.uuid4()}",
                    summary=content, raw_content=content, status=ArticleStatus.PROCESSED,
                    is_selected=True, newsletter_section=section, overall_confidence_score=93,
                    verification_status=VerificationStatus.VERIFIED.value,
                    published_date=datetime.now(timezone.utc),
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

    import app.api.newsletters as nl_module

    nl_module.AsyncSessionLocal = sf
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_generate_and_read_flow(api_client: TestClient) -> None:
    gen = api_client.post("/api/newsletters/generate", json={})
    assert gen.status_code == 200
    body = gen.json()
    nl_id = body["newsletter_id"]
    assert body["version"] == 1
    assert body["word_count"] > 0
    assert body["content"]["cover"]["title"]

    draft = api_client.get(f"/api/newsletters/{nl_id}")
    assert draft.status_code == 200
    assert draft.json()["current_version"] == 1

    versions = api_client.get(f"/api/newsletters/{nl_id}/versions")
    assert versions.status_code == 200 and len(versions.json()) == 1

    linkedin = api_client.get(f"/api/newsletters/{nl_id}/linkedin")
    assert linkedin.status_code == 200
    assert len(linkedin.json()[0]["body"]) <= 1200

    carousel = api_client.get(f"/api/newsletters/{nl_id}/carousel")
    assert carousel.status_code == 200
    assert len(carousel.json()["slides"]) == 10

    subjects = api_client.get(f"/api/newsletters/{nl_id}/subjects")
    assert subjects.status_code == 200
    assert len(subjects.json()["email_subjects"]) == 10

    listing = api_client.get("/api/newsletters")
    assert listing.status_code == 200 and len(listing.json()) >= 1


def test_regenerate_endpoint(api_client: TestClient) -> None:
    nl_id = api_client.post("/api/newsletters/generate", json={}).json()["newsletter_id"]

    regen = api_client.post(
        f"/api/newsletters/{nl_id}/regenerate",
        json={"section": "research", "reason": "refresh", "changed_by": "editor"},
    )
    assert regen.status_code == 200
    assert regen.json()["version"] == 2

    bad = api_client.post(f"/api/newsletters/{nl_id}/regenerate", json={"section": "nope"})
    assert bad.status_code == 422

    stats = api_client.get("/api/newsletters/statistics")
    assert stats.status_code == 200
    assert stats.json()["regenerations_performed"] == 1
    assert stats.json()["newsletters_generated"] == 1


def test_missing_newsletter_404(api_client: TestClient) -> None:
    resp = api_client.get(f"/api/newsletters/{uuid.uuid4()}")
    assert resp.status_code == 404
