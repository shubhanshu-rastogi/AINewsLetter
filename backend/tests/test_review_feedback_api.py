"""Review/feedback API + workflow pause-resume tests."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.review_feedback.review_agent import ReviewAgent
from app.api.deps import get_session
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1},
    "executive_summary": "Weekly briefing.",
    "top_stories": [{"headline": "Agents ship", "what_happened": "x",
                     "citation": {"source_name": "OpenAI", "publication_date": "2026-06-18"}}],
    "tools": [], "testing": {"title": "t", "insight": "i"},
    "research": {"paper": "r", "key_findings": "k"},
    "benchmark": {"title": "b", "what_improved": "w"},
    "trends": [], "final_takeaways": ["a"],
}


@pytest.fixture
def api_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'reviews_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    ids = {}

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            nl = Newsletter(title="AI & Quality Engineering Weekly", issue_number=1)
            s.add(nl)
            await s.flush()
            s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
            await s.commit()
            ids["newsletter_id"] = str(nl.id)
        review = await ReviewAgent(sf).start_review(ids["newsletter_id"])
        ids["review_id"] = review["review_session_id"]

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    import app.api.reviews as reviews_module

    reviews_module.AsyncSessionLocal = sf
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            client.newsletter_id = ids["newsletter_id"]  # type: ignore[attr-defined]
            client.review_id = ids["review_id"]  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_get_review_and_package(api_client: TestClient) -> None:
    rid = api_client.review_id  # type: ignore[attr-defined]
    nid = api_client.newsletter_id  # type: ignore[attr-defined]

    rv = api_client.get(f"/api/reviews/{rid}")
    assert rv.status_code == 200
    assert rv.json()["review_state"] == "pending"

    by_nl = api_client.get(f"/api/reviews/newsletter/{nid}")
    assert by_nl.status_code == 200 and len(by_nl.json()) >= 1

    pkg = api_client.get(f"/api/reviews/{rid}/package")
    assert pkg.status_code == 200
    assert pkg.json()["package"]["title"] == CONTENT["cover"]["title"]


def test_approve_flow(api_client: TestClient) -> None:
    rid = api_client.review_id  # type: ignore[attr-defined]
    resp = api_client.post(f"/api/reviews/{rid}/approve", json={"approval_status": "APPROVED", "comments": "Looks good."})
    assert resp.status_code == 200
    assert resp.json()["review_state"] == "approved"
    assert resp.json()["approved_at"] is not None


def test_reject_flow(api_client: TestClient) -> None:
    rid = api_client.review_id  # type: ignore[attr-defined]
    resp = api_client.post(f"/api/reviews/{rid}/reject", json={"approval_status": "REJECTED", "comments": "No."})
    assert resp.status_code == 200
    assert resp.json()["review_state"] == "rejected"
    assert resp.json()["rejected_at"] is not None


def test_feedback_flow(api_client: TestClient, monkeypatch) -> None:
    rid = api_client.review_id  # type: ignore[attr-defined]

    # Mock targeted regeneration so the endpoint exercises classify/plan/version.
    import app.agents.review_feedback.feedback_agent as fa

    async def no_regen(self, newsletter_id, plan):
        return ["section:executive_summary"]

    monkeypatch.setattr(fa.FeedbackAgent, "execute_plan", no_regen)

    resp = api_client.post(
        f"/api/reviews/{rid}/feedback",
        json={"feedback_items": [
            {"artifact_type": "newsletter_section", "section_name": "Executive Summary",
             "feedback_text": "Make this shorter and more direct.", "severity": "MEDIUM"}
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["actions"]
    assert body["new_review_session_id"]

    versions = api_client.get(f"/api/reviews/{rid}/versions")
    assert versions.status_code == 200 and len(versions.json()) >= 1


def test_security_dependency(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVIEW_AUTH_TOKEN", "s3cret")
    rid = api_client.review_id  # type: ignore[attr-defined]
    try:
        denied = api_client.get(f"/api/reviews/{rid}")
        assert denied.status_code == 401
        ok = api_client.get(f"/api/reviews/{rid}", headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
    finally:
        monkeypatch.setattr(settings, "REVIEW_AUTH_TOKEN", None)


def test_missing_review_404(api_client: TestClient) -> None:
    resp = api_client.get(f"/api/reviews/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- workflow pause + resume (approval routing through the graph) --- #
async def test_workflow_pause_and_approve(workflow_service, session_factory, monkeypatch) -> None:
    from app.agents.source_collection import rss_collector
    from app.models.review_session import ReviewSession
    from sqlalchemy import func, select

    RSS = b"""<?xml version='1.0'?><rss version='2.0'><channel>
    <item><title>Agentic AI orchestration framework launches</title>
    <link>https://openai.com/a1</link><description>Agents orchestration guardrails launch.</description></item>
    </channel></rss>"""

    async def fake_fetch(url, **kw):
        return RSS

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    from app.models.content_source import ContentSource
    from app.models.enums import CollectionMethod, SourceType

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
    state = started["state"]
    assert state["current_step"] == "human_review_node"
    assert state["review_session_id"]

    # A real review session + package were created during the pause.
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(ReviewSession)) >= 1

    # Approve -> workflow resumes and publishes.
    status = await workflow_service.submit_review(started["workflow_run_id"], "approved", [])
    assert status["current_step"] == "completion_node"
    assert status["publish_status"] == "published"
