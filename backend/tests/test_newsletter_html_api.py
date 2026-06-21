"""Tests for the shareable newsletter HTML page endpoint."""

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
from app.models.enums import NewsletterStatus
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft

CONTENT = {
    "cover": {
        "title": "AI & Quality Engineering Weekly",
        "tagline": "Practical AI insights",
        "issue_number": 7,
        "publication_date": "2026-06-21",
        "estimated_reading_time_minutes": 5,
    },
    "executive_summary": "A strong week for agent evaluation tooling.",
    "top_stories": [
        {
            "headline": "Agent eval harness ships",
            "what_happened": "A vendor shipped built-in LLM-as-judge gates.",
            "why_it_matters": "It moves quality checks into CI.",
            "key_takeaway": "Pilot it on a low-risk workflow first.",
            "citation": {"source_name": "Example Source", "source_url": "https://example.com/post"},
        }
    ],
    "tools": [{"name": "EvalKit", "what_it_does": "Scores agent runs.", "use_cases": ["CI gates"], "citation": {}}],
    "final_takeaways": ["Adopt eval gates incrementally."],
}


@pytest.fixture
def html_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'html_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    ids: dict[str, str] = {}

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            nl = Newsletter(title="AI & Quality Engineering Weekly", issue_number=7, status=NewsletterStatus.APPROVED)
            s.add(nl)
            await s.flush()
            s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
            empty = Newsletter(title="No draft yet", issue_number=8, status=NewsletterStatus.DRAFT)
            s.add(empty)
            await s.flush()
            await s.commit()
            ids["with_draft"] = str(nl.id)
            ids["no_draft"] = str(empty.id)

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            client.ids = ids  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_newsletter_html_renders(html_client: TestClient) -> None:
    nid = html_client.ids["with_draft"]  # type: ignore[attr-defined]
    resp = html_client.get(f"/api/newsletters/{nid}/html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "AI &amp; Quality Engineering Weekly" in body
    assert "Issue #7" in body
    assert "Agent eval harness ships" in body
    assert "https://example.com/post" in body
    assert "Adopt eval gates incrementally." in body


def test_newsletter_html_placeholder_without_draft(html_client: TestClient) -> None:
    nid = html_client.ids["no_draft"]  # type: ignore[attr-defined]
    resp = html_client.get(f"/api/newsletters/{nid}/html")
    assert resp.status_code == 200
    assert "not available yet" in resp.text.lower()


def test_newsletter_html_404_for_unknown(html_client: TestClient) -> None:
    resp = html_client.get(f"/api/newsletters/{uuid.uuid4()}/html")
    assert resp.status_code == 404
