"""Publishing agent tests (Beehiiv / LinkedIn / email mocked)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.publishing import beehiiv_publisher, linkedin_publisher, retry_manager
from app.agents.publishing.email_preparer import prepare_email
from app.agents.publishing.exceptions import (
    PermanentPublishError,
    PublicationNotApprovedError,
    RetryablePublishError,
)
from app.agents.publishing.publisher_agent import PublisherAgent
from app.agents.publishing.subscriber_manager import SubscriberManager
from app.core.config import settings
from app.models.carousel_outline import CarouselOutline
from app.models.enums import (
    NewsletterStatus,
    PublishState,
    ReviewState,
    ReviewStatus,
    SubscriberStatus,
    VisualType,
)
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.publication_analytics import PublicationAnalytics
from app.models.publication_failure import PublicationFailure
from app.models.publication_record import PublicationRecord
from app.models.retry_queue import RetryQueueEntry
from app.models.review_session import ReviewSession

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1, "publication_date": "2026-06-18"},
    "executive_summary": "Weekly briefing on agents, evals, and benchmarks.",
    "top_stories": [
        {
            "headline": "Agents ship",
            "what_happened": "Orchestration.",
            "citation": {"source_name": "OpenAI", "publication_date": "2026-06-18"},
        }
    ],
    "tools": [{"name": "Playwright AI", "what_it_does": "Test gen."}],
    "testing": {"title": "t"},
    "research": {"paper": "r"},
    "benchmark": {"title": "b"},
    "trends": [],
    "final_takeaways": ["Pilot first"],
}


async def _seed(session_factory, *, approved=True) -> str:
    async with session_factory() as s:
        nl = Newsletter(
            title="AI & Quality Engineering Weekly",
            issue_number=1,
            status=NewsletterStatus.APPROVED if approved else NewsletterStatus.DRAFT,
        )
        s.add(nl)
        await s.flush()
        nid = str(nl.id)
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
        if approved:
            s.add(
                ReviewSession(
                    newsletter_id=nl.id, review_status=ReviewStatus.APPROVED, review_state=ReviewState.APPROVED.value
                )
            )
        await s.commit()
        return nid


# --- validation --- #
async def test_validation_blocks_unapproved(session_factory) -> None:
    nid = await _seed(session_factory, approved=False)
    with pytest.raises(PublicationNotApprovedError):
        await PublisherAgent(session_factory).validate_publication_package(nid)


async def test_validation_passes_when_approved(session_factory) -> None:
    nid = await _seed(session_factory)
    result = await PublisherAgent(session_factory).validate_publication_package(nid)
    assert result["approved"] and result["valid"]
    assert result["package"]["newsletter_draft"]


# --- channel publishers (simulated) --- #
async def test_beehiiv_simulated_publish() -> None:
    result = await beehiiv_publisher.publish({"title": "x", "newsletter_draft": CONTENT})
    assert result.success and result.status == PublishState.PUBLISHED
    assert result.external_id.startswith("beehiiv-sim-")


async def test_linkedin_simulated_publish() -> None:
    post = await linkedin_publisher.publish_post({"linkedin_post": {"body": "hi"}})
    carousel = await linkedin_publisher.publish_carousel({"carousel_outline": []})
    assert post.external_id.startswith("linkedin-post-sim-")
    assert carousel.external_id.startswith("linkedin-carousel-sim-")


async def test_beehiiv_real_path_mocked(monkeypatch) -> None:
    async def fake_request(payload):
        return "bh-real-123"

    monkeypatch.setattr(beehiiv_publisher, "_beehiiv_request", fake_request)
    monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", True)
    monkeypatch.setattr(settings, "BEEHIIV_API_KEY", "key")
    try:
        result = await beehiiv_publisher.publish({"title": "x", "newsletter_draft": CONTENT})
    finally:
        monkeypatch.setattr(settings, "ENABLE_REAL_PUBLISHING", False)
        monkeypatch.setattr(settings, "BEEHIIV_API_KEY", None)
    assert result.external_id == "bh-real-123"
    assert result.metadata["simulated"] is False


# --- email preparation --- #
def test_email_preparation() -> None:
    pkg = prepare_email(
        {"title": "AI & QE Weekly", "issue_number": 1, "newsletter_draft": CONTENT},
        cover_image_url="https://x/cover.png",
    )
    assert pkg["subject"] == "AI & QE Weekly — Issue 1"
    assert "<h1>" in pkg["html"] and "Agents ship" in pkg["html"]
    assert "Subscribe" in pkg["text"]
    assert pkg["preview_text"]


# --- subscribers --- #
async def test_subscriber_management(session_factory) -> None:
    mgr = SubscriberManager(session_factory)
    sub = await mgr.subscribe("john@example.com", "John Smith", "api")
    assert sub.status == SubscriberStatus.ACTIVE

    # Idempotent re-subscribe.
    again = await mgr.subscribe("john@example.com")
    assert again.id == sub.id

    await mgr.subscribe("jane@example.com")
    stats = await mgr.statistics()
    assert stats["total"] == 2 and stats["active"] == 2

    unsub = await mgr.unsubscribe("john@example.com")
    assert unsub.status == SubscriberStatus.UNSUBSCRIBED and unsub.unsubscribed_at
    assert await mgr.active_count() == 1
    assert await mgr.unsubscribe("missing@example.com") is None


# --- full publish + analytics persistence --- #
async def test_publish_all_channels(session_factory) -> None:
    nid = await _seed(session_factory)
    result = await PublisherAgent(session_factory).publish_newsletter(nid)
    assert result["overall"] == "published"
    assert {c["status"] for c in result["channels"].values()} == {"published"}

    async with session_factory() as s:
        records = (await s.execute(select(PublicationRecord))).scalars().all()
        analytics = await s.scalar(select(func.count()).select_from(PublicationAnalytics))
    assert len(records) == 3
    assert all(r.publish_state == PublishState.PUBLISHED.value for r in records)
    assert analytics == 3


# --- retry logic --- #
async def test_retry_succeeds_after_transient_failure(monkeypatch) -> None:
    monkeypatch.setattr(retry_manager.asyncio, "sleep", _no_sleep)
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RetryablePublishError("temporary")
        return "ok"

    out = await retry_manager.run_with_retry(flaky, max_retries=3)
    assert out == "ok" and attempts["n"] == 3


async def test_retry_not_attempted_on_permanent_error() -> None:
    attempts = {"n": 0}

    async def auth_fail():
        attempts["n"] += 1
        raise PermanentPublishError("auth")

    with pytest.raises(PermanentPublishError):
        await retry_manager.run_with_retry(auth_fail, max_retries=3)
    assert attempts["n"] == 1  # never retried


def test_backoff_is_exponential() -> None:
    assert retry_manager.backoff_delay(1, base=1) == 1
    assert retry_manager.backoff_delay(2, base=1) == 2
    assert retry_manager.backoff_delay(3, base=1) == 4


# --- partial failure --- #
async def test_partial_failure_records_state(session_factory, monkeypatch) -> None:
    nid = await _seed(session_factory)
    monkeypatch.setattr(retry_manager.asyncio, "sleep", _no_sleep)

    async def linkedin_down(package):
        raise RetryablePublishError("LinkedIn down")

    monkeypatch.setattr(linkedin_publisher, "publish_post", linkedin_down)

    result = await PublisherAgent(session_factory).publish_newsletter(nid, ["beehiiv", "linkedin"])
    assert result["overall"] == "partial"
    assert result["channels"]["beehiiv"]["status"] == "published"
    assert result["channels"]["linkedin"]["status"] == "retrying"

    async with session_factory() as s:
        failures = await s.scalar(select(func.count()).select_from(PublicationFailure))
        queued = await s.scalar(select(func.count()).select_from(RetryQueueEntry))
        li = await s.scalar(select(PublicationRecord).where(PublicationRecord.channel == "linkedin"))
        bh = await s.scalar(select(PublicationRecord).where(PublicationRecord.channel == "beehiiv"))
    assert failures == 1 and queued == 1
    assert li.publish_state == PublishState.RETRYING.value
    assert bh.publish_state == PublishState.PUBLISHED.value  # history not corrupted


async def test_permanent_failure_no_retry_queue(session_factory, monkeypatch) -> None:
    nid = await _seed(session_factory)

    async def auth_fail(package):
        raise PermanentPublishError("auth")

    monkeypatch.setattr(beehiiv_publisher, "publish", auth_fail)
    result = await PublisherAgent(session_factory).publish_newsletter(nid, ["beehiiv"])
    assert result["channels"]["beehiiv"]["status"] == "failed"
    async with session_factory() as s:
        queued = await s.scalar(select(func.count()).select_from(RetryQueueEntry))
    assert queued == 0  # permanent errors are not queued


async def test_retry_publication(session_factory, monkeypatch) -> None:
    nid = await _seed(session_factory)
    monkeypatch.setattr(retry_manager.asyncio, "sleep", _no_sleep)
    agent = PublisherAgent(session_factory)
    await agent.publish_newsletter(nid, ["beehiiv"])
    async with session_factory() as s:
        rec = await s.scalar(select(PublicationRecord).where(PublicationRecord.channel == "beehiiv"))
        pub_id = str(rec.id)
    out = await agent.retry_publication(pub_id)
    assert out["channel"] == "beehiiv"
    assert out["result"]["status"] == "published"


async def _no_sleep(_):
    return None
