"""Newsletter writer agent tests (LLM mocked)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.agents.newsletter_writer import llm
from app.agents.newsletter_writer.exceptions import UnknownSectionError
from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent
from app.core.config import settings
from app.models.carousel_outline import CarouselOutline
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod, SourceType, VerificationStatus
from app.models.enums import NewsletterSection as NS
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter_draft import NewsletterDraft
from app.models.newsletter_section import NewsletterSection
from app.models.newsletter_version import NewsletterVersion
from app.models.regeneration_history import RegenerationHistory

SAMPLES = [
    (
        "OpenAI ships Agents SDK with orchestration",
        "OpenAI shipped the Agents SDK with orchestration, guardrails, tracing.",
        NS.AGENTIC_AI_ENGINEERING,
        95,
    ),
    (
        "Playwright adds AI test generation",
        "Playwright generates tests from natural language now.",
        NS.AI_TOOLS_WATCH,
        92,
    ),
    ("LLM-as-judge evaluation matures", "Rubric-based LLM judging with CI quality gates.", NS.AI_TESTING_QUALITY, 93),
    (
        "Enterprise rolls out agentic workflows",
        "A large enterprise deployed agentic workflows with governance.",
        NS.ENTERPRISE_AI_ADOPTION,
        91,
    ),
    (
        "Paper on agent-authored tests",
        "Agents can author maintainable tests with high coverage.",
        NS.RESEARCH_WATCH,
        94,
    ),
    (
        "SWE-bench Verified hits new high",
        "Coding agents improve on SWE-bench Verified; gaps remain.",
        NS.CODING_AGENT_BENCHMARK,
        90,
    ),
    ("Agent observability trends", "Tracing and eval pipelines trend across vendors.", NS.WEEKLY_TREND_SIGNALS, 90),
]


async def _seed(session_factory, *, samples=SAMPLES) -> None:
    async with session_factory() as s:
        src = ContentSource(
            source_name="OpenAI",
            source_type=SourceType.DOCUMENTATION,
            source_url="https://openai.com",
            priority=1,
            credibility_score=0.95,
            freshness_score=0.9,
            relevance_score=0.9,
            preferred_collection_method=CollectionMethod.DOCUMENTATION,
            category="AI",
        )
        s.add(src)
        await s.flush()
        for title, content, section, conf in samples:
            s.add(
                CollectedArticle(
                    source_id=src.id,
                    title=title,
                    url=f"https://openai.com/{uuid.uuid4()}",
                    summary=content,
                    raw_content=content,
                    status=ArticleStatus.PROCESSED,
                    is_selected=True,
                    newsletter_section=section,
                    overall_confidence_score=conf,
                    verification_status=VerificationStatus.VERIFIED.value,
                    published_date=datetime.now(timezone.utc),
                )
            )
        await s.commit()


# --- generation --- #
async def test_newsletter_generation(session_factory) -> None:
    await _seed(session_factory)
    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    content = result["content"]

    assert content["cover"]["title"] == settings.NEWSLETTER_NAME
    assert content["executive_summary"]
    assert 1 <= len(content["top_stories"]) <= 5
    assert content["testing"] and content["enterprise"] and content["research"]
    assert content["benchmark"] and content["trends"]
    assert result["word_count"] > 0
    assert result["reading_time_minutes"] >= 1
    assert result["sections_generated"] >= 7


async def test_executive_summary_within_word_limit(session_factory) -> None:
    await _seed(session_factory)
    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    assert len(result["content"]["executive_summary"].split()) <= 150


async def test_section_content_has_required_fields(session_factory) -> None:
    await _seed(session_factory)
    content = (await NewsletterWriterAgent(session_factory).generate_newsletter())["content"]
    story = content["top_stories"][0]
    for field in (
        "headline",
        "what_happened",
        "why_it_matters",
        "business_impact",
        "engineering_impact",
        "testing_implications",
        "key_takeaway",
        "citation",
    ):
        assert field in story
    assert story["citation"]["source_name"] == "OpenAI"
    assert story["citation"]["source_url"]


# --- LinkedIn / carousel / subjects --- #
async def test_linkedin_post_generation(session_factory) -> None:
    await _seed(session_factory)
    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    post = result["linkedin_post"]
    assert len(post) <= 1200
    assert "Issue" in post
    assert "Subscribe" in post


async def test_carousel_has_ten_slides(session_factory) -> None:
    await _seed(session_factory)
    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    assert len(result["carousel"]) == 10
    assert result["carousel"][0]["slide"] == 1


async def test_email_subjects(session_factory) -> None:
    await _seed(session_factory)
    result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    assert len(result["email_subjects"]) == 10


# --- persistence --- #
async def test_database_persistence(session_factory) -> None:
    await _seed(session_factory)
    await NewsletterWriterAgent(session_factory).generate_newsletter()
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(NewsletterDraft)) == 1
        assert await s.scalar(select(func.count()).select_from(NewsletterVersion)) == 1
        assert await s.scalar(select(func.count()).select_from(LinkedInPost)) == 1
        assert await s.scalar(select(func.count()).select_from(CarouselOutline)) == 1
        assert await s.scalar(select(func.count()).select_from(NewsletterSection)) >= 7


# --- versioning + regeneration --- #
async def test_regeneration_bumps_version_and_logs(session_factory) -> None:
    await _seed(session_factory)
    agent = NewsletterWriterAgent(session_factory)
    gen = await agent.generate_newsletter()
    nl_id = gen["newsletter_id"]

    out = await agent.regenerate_section(nl_id, "trends", reason="freshen trends", changed_by="editor")
    assert out["version"] == 2

    async with session_factory() as s:
        draft = await s.scalar(select(NewsletterDraft).where(NewsletterDraft.newsletter_id == uuid.UUID(nl_id)))
        assert draft.current_version == 2
        versions = await s.scalar(select(func.count()).select_from(NewsletterVersion))
        history = (await s.execute(select(RegenerationHistory))).scalars().all()
    assert versions == 2
    assert len(history) == 1
    assert history[0].section_name == "trends"
    assert history[0].from_version == 1 and history[0].to_version == 2
    assert history[0].changed_by == "editor"


async def test_regenerate_unknown_section_raises(session_factory) -> None:
    await _seed(session_factory)
    agent = NewsletterWriterAgent(session_factory)
    gen = await agent.generate_newsletter()
    with pytest.raises(UnknownSectionError):
        await agent.regenerate_section(gen["newsletter_id"], "nonsense", reason="x")


# --- content rules: review_required marking --- #
async def test_review_required_articles_marked(session_factory) -> None:
    await _seed(
        session_factory,
        samples=[
            ("Agentic AI orchestration update", "An orchestration update for agents.", NS.AGENTIC_AI_ENGINEERING, 75),
        ],
    )
    async with session_factory() as s:
        art = (await s.execute(select(CollectedArticle))).scalar_one()
        art.verification_status = VerificationStatus.REVIEW_REQUIRED.value
        await s.commit()

    content = (await NewsletterWriterAgent(session_factory).generate_newsletter())["content"]
    assert content["top_stories"][0]["needs_review"] is True


# --- workflow integration --- #
async def test_workflow_integration(workflow_service, session_factory, monkeypatch) -> None:
    from app.agents.source_collection import rss_collector

    RSS = b"""<?xml version='1.0'?><rss version='2.0'><channel>
    <item><title>Agentic AI orchestration framework launches</title>
    <link>https://openai.com/a1</link><description>Agents orchestration guardrails launch.</description></item>
    </channel></rss>"""

    async def fake_fetch(url, **kw):
        return RSS

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    async with session_factory() as s:
        s.add(
            ContentSource(
                source_name="OpenAI",
                source_type=SourceType.RSS,
                source_url="https://openai.com",
                rss_url="https://openai.com/feed",
                priority=1,
                credibility_score=0.95,
                freshness_score=0.9,
                relevance_score=0.9,
                preferred_collection_method=CollectionMethod.RSS,
                fallback_collection_method=CollectionMethod.WEB,
                category="AI",
            )
        )
        await s.commit()

    result = await workflow_service.start_newsletter_workflow()
    state = result["state"]
    assert state["current_step"] == "human_review_node"
    # Newsletter writer ran: draft + linkedin present in state.
    assert state.get("newsletter_draft") is not None
    assert "cover" in state["newsletter_draft"]
    assert state.get("linkedin_draft", {}).get("body")


# --- LLM polish (mocked) --- #
async def test_llm_polish(session_factory, monkeypatch) -> None:
    async def fake_polish(text, brand):
        return "POLISHED: " + text

    monkeypatch.setattr(llm, "polish_text", fake_polish)
    monkeypatch.setattr(settings, "ENABLE_LLM_WRITER", True)
    try:
        await _seed(session_factory)
        result = await NewsletterWriterAgent(session_factory).generate_newsletter()
    finally:
        monkeypatch.setattr(settings, "ENABLE_LLM_WRITER", False)
    assert result["content"]["executive_summary"].startswith("POLISHED:")
