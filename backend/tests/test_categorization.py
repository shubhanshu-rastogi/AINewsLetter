"""Categorization agent tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents.categorization import classifier, llm
from app.agents.categorization.categorization_agent import CategorizationAgent
from app.agents.categorization.tagger import tags_for
from app.core.config import settings
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import (
    ArticleStatus,
    CollectionMethod,
    NewsletterSection,
    SourceType,
)


def _source() -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        source_name="S",
        source_type=SourceType.RSS,
        source_url="https://ex.com",
        priority=1,
        credibility_score=0.8,
        freshness_score=0.8,
        relevance_score=0.8,
        preferred_collection_method=CollectionMethod.RSS,
    )


def _article(title, content="") -> CollectedArticle:
    src = _source()
    return CollectedArticle(
        id=uuid.uuid4(),
        source_id=src.id,
        title=title,
        url=f"https://ex.com/{uuid.uuid4()}",
        raw_content=content,
        summary=content,
        source=src,
    )


# --- classification (matches the prompt's examples) --- #
@pytest.mark.parametrize(
    "title, content, expected",
    [
        ("OpenAI Agents Guide", "agent orchestration guardrails tool use",
         NewsletterSection.AGENTIC_AI_ENGINEERING),
        ("Google Evaluation Docs", "evaluation rubric metrics pass rate llm-as-judge",
         NewsletterSection.AI_EVALUATION_QA_GATES),
        ("Ministry of Testing", "test automation quality engineering playwright qa ",
         NewsletterSection.AI_TESTING_QUALITY),
        ("SWE-bench results", "swe-bench coding agent leaderboard benchmark pass@",
         NewsletterSection.CODING_AGENT_BENCHMARK),
    ],
)
def test_classification(title, content, expected) -> None:
    result = classifier.classify(_article(title, content))
    assert result.newsletter_section == expected
    assert result.primary_category


def test_tag_generation() -> None:
    article = _article("Agent orchestration", "agents orchestration evaluation playwright observability")
    tags = tags_for(article)
    assert "agents" in tags
    assert "orchestration" in tags
    assert "evaluation" in tags
    assert "playwright" in tags
    assert "observability" in tags


def test_section_assignment_helper() -> None:
    agent = CategorizationAgent(lambda: None)
    section = agent.assign_newsletter_section(
        _article("Enterprise AI adoption", "enterprise governance adoption architecture production")
    )
    assert section == NewsletterSection.ENTERPRISE_AI_ADOPTION


# --- DB persistence --- #
async def test_categorization_agent_persists(session_factory) -> None:
    async with session_factory() as s:
        src = _source()
        s.add(src)
        await s.flush()
        s.add(
            CollectedArticle(
                source_id=src.id,
                title="Multi-agent orchestration with guardrails",
                url="https://ex.com/x",
                raw_content="agents orchestration guardrails evaluation",
                status=ArticleStatus.PROCESSED,
                is_selected=True,
            )
        )
        await s.commit()

    agent = CategorizationAgent(session_factory)
    result = await agent.run()
    assert result["classified"] == 1

    async with session_factory() as s:
        article = (await s.execute(select(CollectedArticle))).scalar_one()
    assert article.primary_category == "Agentic AI Engineering"
    assert article.newsletter_section == NewsletterSection.AGENTIC_AI_ENGINEERING
    assert "agents" in (article.keywords or [])
    assert article.topics


# --- LLM enrichment path (mocked) --- #
async def test_llm_enrichment_merges_keywords(session_factory, monkeypatch) -> None:
    async def fake_llm(article):
        return {"keywords": ["custom-llm-tag"], "topics": ["LLM Topic"]}

    monkeypatch.setattr(llm, "llm_classify", fake_llm)
    monkeypatch.setattr(settings, "ENABLE_LLM_CLASSIFICATION", True)

    async with session_factory() as s:
        src = _source()
        s.add(src)
        await s.flush()
        s.add(
            CollectedArticle(
                source_id=src.id,
                title="Agent evaluation",
                url="https://ex.com/llm",
                raw_content="agents evaluation",
                is_selected=True,
            )
        )
        await s.commit()

    try:
        agent = CategorizationAgent(session_factory)
        await agent.run()
    finally:
        monkeypatch.setattr(settings, "ENABLE_LLM_CLASSIFICATION", False)

    async with session_factory() as s:
        article = (await s.execute(select(CollectedArticle))).scalar_one()
    assert "custom-llm-tag" in article.keywords
    assert "LLM Topic" in article.topics
