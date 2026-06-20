"""Extra coverage: payload builders, real-path mocks, error wrapping, helpers."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.agents.publishing import beehiiv_publisher, linkedin_publisher, publication_tracker
from app.agents.publishing.exceptions import RetryablePublishError
from app.agents.publishing.publisher_agent import PublisherAgent
from app.core.config import settings
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
    "cover": {"title": "AI & QE Weekly", "issue_number": 1, "publication_date": "2026-06-18"},
    "executive_summary": "Briefing.",
    "top_stories": [{"headline": "Agents ship", "what_happened": "x"}],
    "tools": [{"name": "Tool", "what_it_does": "y"}],
    "testing": {"title": "t"},
    "research": {"paper": "r"},
    "benchmark": {"title": "b"},
    "trends": [],
    "final_takeaways": ["z"],
}
PACKAGE = {
    "title": "AI & QE Weekly",
    "issue_number": 1,
    "newsletter_draft": CONTENT,
    "linkedin_post": {"body": "post", "hashtags": ["#AI"]},
    "carousel_outline": [{"slide": 1}],
    "visuals": [],
    "cover_image_url": "https://x/cover.png",
}


async def _seed(session_factory) -> str:
    async with session_factory() as s:
        nl = Newsletter(title="AI & QE Weekly", issue_number=1, status=NewsletterStatus.APPROVED)
        s.add(nl)
        await s.flush()
        s.add(NewsletterDraft(newsletter_id=nl.id, content=CONTENT, current_version=1))
        s.add(LinkedInPost(newsletter_id=nl.id, body="post", hashtags=["#AI"]))
        s.add(CarouselOutline(newsletter_id=nl.id, slides=[{"slide": 1}]))
        s.add(
            GeneratedVisual(
                newsletter_id=nl.id,
                visual_type=VisualType.HERO,
                visual_kind="cover",
                file_path="/x/cover.png",
                width=1200,
                height=630,
                version=1,
            )
        )
        s.add(
            ReviewSession(
                newsletter_id=nl.id, review_status=ReviewStatus.APPROVED, review_state=ReviewState.APPROVED.value
            )
        )
        await s.commit()
        return str(nl.id)


# --- payload builders --- #
def test_payload_builders() -> None:
    bh = beehiiv_publisher.build_payload(PACKAGE)
    assert bh["title"] and bh["cta"]["url"] and bh["tags"]

    post = linkedin_publisher.build_post_payload(PACKAGE)
    assert post["text"] == "post" and post["hashtags"] == ["#AI"]
    carousel = linkedin_publisher.build_carousel_payload(PACKAGE)
    assert "slides" in carousel


# --- real path (request mocked) --- #
async def test_linkedin_real_path_mocked(monkeypatch) -> None:
    async def fake_request(endpoint, payload):
        return f"li-{endpoint}"

    monkeypatch.setattr(linkedin_publisher, "_linkedin_request", fake_request)
    monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", True)
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "tok")
    try:
        post = await linkedin_publisher.publish_post(PACKAGE)
        carousel = await linkedin_publisher.publish_carousel(PACKAGE)
    finally:
        monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", False)
        monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", None)
    assert post.external_id == "li-ugcPosts" and post.metadata["simulated"] is False
    assert carousel.external_id == "li-assets"


# --- error wrapping (httpx -> RetryablePublishError) --- #
async def test_beehiiv_wraps_httpx_error(monkeypatch) -> None:
    async def boom(payload):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(beehiiv_publisher, "_beehiiv_request", boom)
    monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", True)
    monkeypatch.setattr(settings, "BEEHIIV_API_KEY", "key")
    try:
        with pytest.raises(RetryablePublishError):
            await beehiiv_publisher.publish(PACKAGE)
    finally:
        monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", False)
        monkeypatch.setattr(settings, "BEEHIIV_API_KEY", None)


async def test_linkedin_wraps_httpx_error(monkeypatch) -> None:
    async def boom(endpoint, payload):
        raise httpx.ConnectError("network")

    monkeypatch.setattr(linkedin_publisher, "_linkedin_request", boom)
    monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", True)
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "tok")
    try:
        with pytest.raises(RetryablePublishError):
            await linkedin_publisher.publish_post(PACKAGE)
    finally:
        monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", False)
        monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", None)


# --- publication tracker helpers --- #
async def test_publication_tracker_helpers(session_factory) -> None:
    nid = await _seed(session_factory)
    await PublisherAgent(session_factory).publish_newsletter(nid, ["beehiiv"])
    async with session_factory() as s:
        all_pubs = await publication_tracker.list_publications(s)
        for_nl = await publication_tracker.for_newsletter(s, uuid.UUID(nid))
    assert len(all_pubs) >= 1
    assert len(for_nl) == 1


# --- agent helper methods --- #
async def test_agent_helpers(session_factory) -> None:
    nid = await _seed(session_factory)
    agent = PublisherAgent(session_factory)

    email = await agent.prepare_email(nid)
    assert email["subject"]

    post_result = await agent.publish_linkedin_post(nid)
    assert post_result["overall"] in ("published", "partial")

    carousel = await agent.publish_carousel(nid)
    assert carousel.external_id

    analytics = await agent.collect_analytics(nid, "linkedin")
    assert analytics["channel"] == "linkedin"

    assert agent.update_workflow_state("published") == {"publish_status": "published"}
