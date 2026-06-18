"""Publishing + subscriber API tests, plus workflow publish integration."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.db.base import Base
from app.main import app
from app.models.carousel_outline import CarouselOutline
from app.models.enums import (
    NewsletterStatus,
    ReviewState,
    ReviewStatus,
    VisualType,
)
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.review_session import ReviewSession

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1},
    "executive_summary": "Briefing.",
    "top_stories": [{"headline": "Agents ship", "what_happened": "x"}],
    "tools": [], "testing": {"title": "t"}, "research": {"paper": "r"},
    "benchmark": {"title": "b"}, "trends": [], "final_takeaways": ["z"],
}


@pytest.fixture
def api_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'pub_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    ids = {}

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            nl = Newsletter(title="AI & Quality Engineering Weekly", issue_number=1,
                            status=NewsletterStatus.APPROVED)
            s.add(nl)
            await s.flush()
            s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
            s.add(LinkedInPost(newsletter_id=nl.id, body="post", hashtags=["#AI"]))
            s.add(CarouselOutline(newsletter_id=nl.id, slides=[{"slide": 1}]))
            s.add(GeneratedVisual(newsletter_id=nl.id, visual_type=VisualType.HERO,
                                  visual_kind="cover", file_path="/x/cover.png", width=1200, height=630, version=1))
            s.add(ReviewSession(newsletter_id=nl.id, review_status=ReviewStatus.APPROVED,
                                review_state=ReviewState.APPROVED.value))
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

    import app.api.publishing as pub_module
    import app.api.subscribers as sub_module

    pub_module.AsyncSessionLocal = sf
    sub_module.AsyncSessionLocal = sf
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            client.newsletter_id = ids["newsletter_id"]  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_publish_flow(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]

    resp = api_client.post(f"/api/publish/{nid}", json={"channels": ["BEEHIIV", "LINKEDIN"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"] == "published"
    assert set(body["channels"]) == {"beehiiv", "linkedin"}

    pubs = api_client.get(f"/api/publications/{nid}")
    assert pubs.status_code == 200 and len(pubs.json()) == 2
    assert pubs.json()[0]["external_publication_id"]

    analytics = api_client.get(f"/api/publications/{nid}/analytics")
    assert analytics.status_code == 200 and len(analytics.json()) == 2
    assert analytics.json()[0]["is_placeholder"] is True

    all_pubs = api_client.get("/api/publications")
    assert all_pubs.status_code == 200 and len(all_pubs.json()) >= 2


def test_publish_unapproved_returns_409(api_client: TestClient) -> None:
    import app.api.publishing as pub_module

    async def _make_draft() -> str:
        async with pub_module.AsyncSessionLocal() as s:
            nl = Newsletter(title="Draft", issue_number=2, status=NewsletterStatus.DRAFT)
            s.add(nl)
            await s.flush()
            s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
            await s.commit()
            return str(nl.id)

    nid = asyncio.run(_make_draft())
    resp = api_client.post(f"/api/publish/{nid}")
    assert resp.status_code == 409


def test_email_endpoint(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]
    resp = api_client.post(f"/api/publish/{nid}/email")
    assert resp.status_code == 200
    assert resp.json()["subject"]
    assert "<h1>" in resp.json()["html"]


def test_subscriber_endpoints(api_client: TestClient) -> None:
    sub = api_client.post("/api/subscribers", json={"email": "john@example.com", "name": "John Smith"})
    assert sub.status_code == 201
    assert sub.json()["status"] == "active"

    api_client.post("/api/subscribers", json={"email": "jane@example.com"})

    listing = api_client.get("/api/subscribers")
    assert listing.status_code == 200 and len(listing.json()) == 2

    stats = api_client.get("/api/subscribers/stats")
    assert stats.status_code == 200 and stats.json()["active"] == 2

    unsub = api_client.post("/api/subscribers/unsubscribe", json={"email": "john@example.com"})
    assert unsub.status_code == 200 and unsub.json()["status"] == "unsubscribed"

    missing = api_client.post("/api/subscribers/unsubscribe", json={"email": "nobody@example.com"})
    assert missing.status_code == 404


def test_retry_endpoint(api_client: TestClient) -> None:
    nid = api_client.newsletter_id  # type: ignore[attr-defined]
    api_client.post(f"/api/publish/{nid}", json={"channels": ["BEEHIIV"]})
    pubs = api_client.get(f"/api/publications/{nid}").json()
    pub_id = pubs[0]["id"]
    retry = api_client.post(f"/api/publications/{pub_id}/retry")
    assert retry.status_code == 200


# --- workflow integration: approve resumes -> publisher publishes --- #
async def test_workflow_publishes_after_approval(workflow_service, session_factory, monkeypatch) -> None:
    from sqlalchemy import func, select

    from app.agents.source_collection import rss_collector
    from app.models.content_source import ContentSource
    from app.models.enums import CollectionMethod, SourceType
    from app.models.publication_record import PublicationRecord

    RSS = b"""<?xml version='1.0'?><rss version='2.0'><channel>
    <item><title>Agentic AI orchestration launches</title><link>https://openai.com/a1</link>
    <description>Agents orchestration launch.</description></item></channel></rss>"""

    async def fake_fetch(url, **kw):
        return RSS

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    async with session_factory() as s:
        s.add(ContentSource(
            source_name="OpenAI", source_type=SourceType.RSS, source_url="https://openai.com",
            rss_url="https://openai.com/feed", priority=1, credibility_score=0.95,
            freshness_score=0.9, relevance_score=0.9,
            preferred_collection_method=CollectionMethod.RSS,
            fallback_collection_method=CollectionMethod.WEB, category="AI",
        ))
        await s.commit()

    started = await workflow_service.start_newsletter_workflow()
    assert started["state"]["current_step"] == "human_review_node"

    status = await workflow_service.submit_review(started["workflow_run_id"], "approved", [])
    assert status["current_step"] == "completion_node"
    assert status["publish_status"] == "published"

    async with session_factory() as s:
        records = await s.scalar(select(func.count()).select_from(PublicationRecord))
    assert records == 3  # beehiiv + linkedin + email
