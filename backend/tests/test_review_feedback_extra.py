"""Extra coverage: real targeted regeneration, review getters, notion failure."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent
from app.agents.review_feedback import notion_review
from app.agents.review_feedback.feedback_agent import FeedbackAgent
from app.agents.review_feedback.review_agent import ReviewAgent
from app.agents.visual_generation.visual_agent import VisualGenerationAgent
from app.core.config import settings
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import (
    ArticleStatus,
    CollectionMethod,
    NewsletterSection as NS,
    ResolutionStatus,
    SourceType,
    VerificationStatus,
)
from app.models.feedback_item import FeedbackItem
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.review_session import ReviewSession

SAMPLES = [
    ("Agentic AI orchestration ships", NS.AGENTIC_AI_ENGINEERING, 95),
    ("Playwright AI testing tool", NS.AI_TOOLS_WATCH, 92),
    ("Research: agent-authored tests", NS.RESEARCH_WATCH, 94),
    ("Research: eval methods survey", NS.RESEARCH_WATCH, 90),  # second research article
    ("SWE-bench new high", NS.CODING_AGENT_BENCHMARK, 91),
]


async def _build_full_newsletter(session_factory) -> str:
    """Seed verified articles, then run writer + visual agents to build everything."""
    async with session_factory() as s:
        src = ContentSource(
            source_name="OpenAI", source_type=SourceType.DOCUMENTATION,
            source_url="https://openai.com", priority=1, credibility_score=0.95,
            freshness_score=0.9, relevance_score=0.9,
            preferred_collection_method=CollectionMethod.DOCUMENTATION, category="AI",
        )
        s.add(src)
        await s.flush()
        for i, (title, section, conf) in enumerate(SAMPLES):
            s.add(CollectedArticle(
                source_id=src.id, title=title, url=f"https://openai.com/{i}",
                summary="Summary text.", raw_content="content " * 30,
                status=ArticleStatus.PROCESSED,
                # Only first research article is selected initially.
                is_selected=(title != "Research: eval methods survey"),
                newsletter_section=section, overall_confidence_score=conf,
                verification_status=VerificationStatus.VERIFIED.value,
                published_date=datetime.now(timezone.utc),
            ))
        await s.commit()

    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    nid = result["newsletter_id"]
    await VisualGenerationAgent(session_factory).generate_all_visuals(nid)
    return nid


async def test_real_targeted_regeneration(session_factory) -> None:
    nid = await _build_full_newsletter(session_factory)
    agent = FeedbackAgent(session_factory)

    # Section regeneration (writer).
    await agent.regenerate_newsletter_section(nid, "research", "freshen")

    # LinkedIn regeneration updates the stored post.
    await agent.regenerate_linkedin_post(nid)
    async with session_factory() as s:
        post = await s.scalar(select(LinkedInPost).where(LinkedInPost.newsletter_id == uuid.UUID(nid)))
    assert post is not None and post.body

    # Carousel slide + cover regeneration version the visuals.
    await agent.regenerate_carousel_slide(nid, 1)
    await agent.regenerate_cover_image(nid)
    async with session_factory() as s:
        cover = await s.scalar(select(GeneratedVisual).where(
            GeneratedVisual.newsletter_id == uuid.UUID(nid),
            GeneratedVisual.visual_kind == "cover"))
    assert cover.version >= 2

    # Replace article swaps the selected research article.
    await agent.replace_article_and_regenerate_section(nid, "research")
    async with session_factory() as s:
        selected = (await s.execute(select(CollectedArticle).where(
            CollectedArticle.newsletter_section == NS.RESEARCH_WATCH,
            CollectedArticle.is_selected.is_(True)))).scalars().all()
    assert len(selected) == 1
    assert selected[0].title == "Research: eval methods survey"  # swapped to the alternative


async def test_process_feedback_with_stored_items(session_factory) -> None:
    nid = await _build_full_newsletter(session_factory)
    review = await ReviewAgent(session_factory).start_review(nid)
    rid = review["review_session_id"]

    # Pre-persist a feedback item, then process without passing items.
    async with session_factory() as s:
        s.add(FeedbackItem(
            review_session_id=uuid.UUID(rid),
            feedback_text="Make the executive summary shorter.",
            resolution_status=ResolutionStatus.OPEN,
        ))
        await s.commit()

    agent = FeedbackAgent(session_factory)
    result = await agent.process_feedback(rid, items=None, create_new_session=False)
    assert result["plan"]["actions"]
    assert result["new_review_session_id"] is None


async def test_review_getters(session_factory) -> None:
    nid = await _build_full_newsletter(session_factory)
    agent = ReviewAgent(session_factory)
    review = await agent.start_review(nid)
    rid = review["review_session_id"]

    session = await agent.get_session(rid)
    assert str(session.id) == rid
    package = await agent.get_package(rid)
    assert package["title"]
    sessions = await agent.list_for_newsletter(nid)
    assert len(sessions) >= 1


async def test_notion_create_failure_falls_back(monkeypatch) -> None:
    async def boom(payload):
        raise RuntimeError("notion down")

    monkeypatch.setattr(notion_review, "_notion_create_page", boom)
    monkeypatch.setattr(settings, "NOTION_API_KEY", "secret")
    monkeypatch.setattr(settings, "NOTION_REVIEW_DATABASE_ID", "db123")
    try:
        url = await notion_review.create_review_page(
            {"title": "x", "issue_number": 1, "newsletter_draft": {}, "fact_check": {}, "approval_options": []}
        )
    finally:
        monkeypatch.setattr(settings, "NOTION_API_KEY", None)
        monkeypatch.setattr(settings, "NOTION_REVIEW_DATABASE_ID", None)
    assert url is None
