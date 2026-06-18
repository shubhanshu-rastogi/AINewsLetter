"""Extra direct coverage: stats, LLM provider branches, all regen sections, brand."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.agents.newsletter_writer import llm
from app.agents.newsletter_writer.brand import load_brand
from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent
from app.core.config import settings
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod
from app.models.enums import NewsletterSection as NS
from app.models.enums import SourceType, VerificationStatus
from app.services.newsletter_stats import get_newsletter_stats

SAMPLES = [
    ("OpenAI ships Agents SDK", "Orchestration, guardrails, tracing.", NS.AGENTIC_AI_ENGINEERING),
    ("Playwright AI test gen", "Generate tests from natural language.", NS.AI_TOOLS_WATCH),
    ("LLM-as-judge matures", "Rubric judging + CI gates.", NS.AI_TESTING_QUALITY),
    ("Enterprise agentic rollout", "Governance + measured ROI.", NS.ENTERPRISE_AI_ADOPTION),
    ("Agent-authored tests paper", "Agents author maintainable tests.", NS.RESEARCH_WATCH),
    ("SWE-bench new high", "Coding agents improve; gaps remain.", NS.CODING_AGENT_BENCHMARK),
    ("Observability trend", "Tracing and eval pipelines trend.", NS.WEEKLY_TREND_SIGNALS),
]


async def _seed(session_factory) -> None:
    async with session_factory() as s:
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


def test_brand_voice_guidelines() -> None:
    brand = load_brand()
    guide = brand.voice_guidelines()
    assert brand.name in guide
    assert "Audience" in guide


@pytest.mark.parametrize(
    "section",
    ["executive_summary", "top_stories", "tools", "testing", "enterprise",
     "research", "benchmark", "trends", "final_takeaways"],
)
async def test_regenerate_every_section(session_factory, section) -> None:
    await _seed(session_factory)
    agent = NewsletterWriterAgent(session_factory)
    gen = await agent.generate_newsletter()
    out = await agent.regenerate_section(gen["newsletter_id"], section, reason="r")
    assert out["section"] == section
    assert out["version"] == 2


async def test_newsletter_stats_direct(session_factory) -> None:
    await _seed(session_factory)
    agent = NewsletterWriterAgent(session_factory)
    gen = await agent.generate_newsletter()
    await agent.regenerate_section(gen["newsletter_id"], "trends", reason="r")

    async with session_factory() as s:
        stats = await get_newsletter_stats(s)
    assert stats.newsletters_generated == 1
    assert stats.regenerations_performed == 1
    assert stats.average_word_count > 0
    assert stats.top_sections_regenerated.get("trends") == 1


async def test_llm_anthropic_polish(monkeypatch) -> None:
    async def fake(text, brand):
        return "A:" + text

    monkeypatch.setattr(llm, "_anthropic_polish", fake)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    assert await llm.polish_text("hi", load_brand()) == "A:hi"


async def test_llm_openai_polish(monkeypatch) -> None:
    async def fake(text, brand):
        return "O:" + text

    monkeypatch.setattr(llm, "_openai_polish", fake)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    try:
        assert await llm.polish_text("hi", load_brand()) == "O:hi"
    finally:
        monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")


async def test_llm_polish_returns_input_on_error(monkeypatch) -> None:
    async def boom(text, brand):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "_anthropic_polish", boom)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    assert await llm.polish_text("hi", load_brand()) == "hi"
