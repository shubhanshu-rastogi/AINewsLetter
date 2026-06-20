"""Extra direct tests to cover stats, LLM provider branches, and exceptions."""

from __future__ import annotations

import uuid

import pytest

from app.agents.categorization import llm
from app.agents.categorization.categorization_agent import CategorizationAgent
from app.agents.categorization.exceptions import CategorizationError, ClassificationError
from app.agents.categorization.tagger import topics_for
from app.agents.relevance_filter.exceptions import RelevanceError, ScoringError
from app.agents.relevance_filter.filter_agent import RelevanceFilterAgent
from app.core.config import settings
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod, SourceType
from app.services.relevance_stats import (
    get_categories_distribution,
    get_relevance_stats,
    get_trends,
)


def _source() -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        source_name="S",
        source_type=SourceType.DOCUMENTATION,
        source_url="https://ex.com",
        priority=1,
        credibility_score=0.9,
        freshness_score=0.8,
        relevance_score=0.9,
        preferred_collection_method=CollectionMethod.DOCUMENTATION,
        category="Agentic AI Engineering",
    )


async def _seed(session_factory) -> None:
    async with session_factory() as s:
        src = _source()
        s.add(src)
        await s.flush()
        for i in range(3):
            s.add(
                CollectedArticle(
                    source_id=src.id,
                    title=f"AI agent orchestration evaluation {i}",
                    url=f"https://ex.com/x{i}",
                    raw_content="agents orchestration architecture evaluation enterprise testing " * 8,
                    status=ArticleStatus.NEW,
                    credibility_score=0.9,
                    source_category="Agentic AI Engineering",
                )
            )
        await s.commit()


def test_topics_for() -> None:
    art = CollectedArticle(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        title="Enterprise AI testing",
        url="https://ex.com/t",
        raw_content="enterprise governance testing quality engineering agents",
    )
    topics = topics_for(art)
    assert topics and len(topics) <= 3


def test_exceptions_hierarchy() -> None:
    assert issubclass(ScoringError, RelevanceError)
    assert issubclass(ClassificationError, CategorizationError)
    with pytest.raises(RelevanceError):
        raise ScoringError("x")


async def test_score_all_and_select_all(session_factory) -> None:
    await _seed(session_factory)
    agent = RelevanceFilterAgent(session_factory)

    scored = await agent.score_all()
    assert scored["scored"] == 3

    selected = await agent.select_all()
    assert len(selected["selected_article_ids"]) >= 1

    # select_all with explicit ids branch
    ids = selected["selected_article_ids"]
    again = await agent.select_all(ids)
    assert again["selected_article_ids"]


async def test_relevance_stats_aggregations(session_factory) -> None:
    await _seed(session_factory)
    await RelevanceFilterAgent(session_factory).run()
    await CategorizationAgent(session_factory).run()

    async with session_factory() as s:
        stats = await get_relevance_stats(s)
        cats = await get_categories_distribution(s)
        trends = await get_trends(s)

    assert stats["total_articles"] == 3
    assert stats["articles_scored"] == 3
    assert stats["average_relevance_score"] > 0
    assert isinstance(stats["top_keywords"], dict)
    assert "by_section" in cats
    assert "top_trending" in trends


async def test_llm_anthropic_branch(monkeypatch) -> None:
    async def fake_anthropic(prompt):
        return '{"keywords": ["a"], "topics": ["T"]}'

    monkeypatch.setattr(llm, "_anthropic_complete", fake_anthropic)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    art = CollectedArticle(id=uuid.uuid4(), source_id=uuid.uuid4(), title="t", url="u")
    result = await llm.llm_classify(art)
    assert result == {"keywords": ["a"], "topics": ["T"]}


async def test_llm_openai_branch(monkeypatch) -> None:
    async def fake_openai(prompt):
        return '{"keywords": ["b"]}'

    monkeypatch.setattr(llm, "_openai_complete", fake_openai)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    try:
        art = CollectedArticle(id=uuid.uuid4(), source_id=uuid.uuid4(), title="t", url="u")
        result = await llm.llm_classify(art)
    finally:
        monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    assert result == {"keywords": ["b"]}


async def test_llm_returns_none_on_error(monkeypatch) -> None:
    async def boom(prompt):
        raise RuntimeError("api down")

    monkeypatch.setattr(llm, "_anthropic_complete", boom)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    art = CollectedArticle(id=uuid.uuid4(), source_id=uuid.uuid4(), title="t", url="u")
    assert await llm.llm_classify(art) is None
