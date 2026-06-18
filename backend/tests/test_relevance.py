"""Relevance filter agent tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.agents.relevance_filter import duplicate_detector, ranking_engine, scoring_engine
from app.agents.relevance_filter.article_selector import select_articles
from app.agents.relevance_filter.filter_agent import RelevanceFilterAgent
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import (
    ArticleStatus,
    CollectionMethod,
    NewsletterSection,
    SourceType,
)


def _source(source_type=SourceType.RSS, credibility=0.8) -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        source_name="S",
        source_type=source_type,
        source_url="https://ex.com",
        priority=1,
        credibility_score=credibility,
        freshness_score=0.8,
        relevance_score=0.8,
        preferred_collection_method=CollectionMethod.RSS,
    )


def _article(
    title="Agent orchestration guide",
    content="agents orchestration architecture evaluation",
    *,
    url="https://ex.com/a",
    credibility=0.8,
    published=None,
    section=None,
    source=None,
    overall=None,
) -> CollectedArticle:
    src = source or _source(credibility=credibility)
    article = CollectedArticle(
        id=uuid.uuid4(),
        source_id=src.id,
        title=title,
        url=url,
        raw_content=content,
        summary=content,
        credibility_score=credibility,
        published_date=published,
        newsletter_section=section,
        source=src,
    )
    article.source = src
    if overall is not None:
        article.overall_relevance_score = overall
    return article


# --- scoring --- #
def test_relevance_scoring_dimensions() -> None:
    now = datetime.now(timezone.utc)
    article = _article(
        title="Building effective AI agents: orchestration and evaluation",
        content="agents orchestration architecture evaluation benchmark testing enterprise " * 5,
        published=now,
        credibility=0.95,
        source=_source(SourceType.DOCUMENTATION, credibility=0.95),
    )
    breakdown = scoring_engine.score_article(article, now=now)

    for value in (
        breakdown.credibility_score,
        breakdown.newsletter_relevance_score,
        breakdown.technical_depth_score,
        breakdown.overall_relevance_score,
    ):
        assert 0 <= value <= 100
    assert breakdown.credibility_score >= 90  # high-credibility source
    assert breakdown.overall_relevance_score > 40


def test_freshness_scoring() -> None:
    now = datetime.now(timezone.utc)
    fresh = scoring_engine.freshness_dimension(now, now=now)
    week = scoring_engine.freshness_dimension(now - timedelta(days=7), now=now)
    stale = scoring_engine.freshness_dimension(now - timedelta(days=25), now=now)
    assert fresh == 100.0
    assert fresh > week > stale
    assert stale < 30  # penalized past 14 days
    assert scoring_engine.freshness_dimension(None) == 50.0


def test_clickbait_penalty() -> None:
    now = datetime.now(timezone.utc)
    article = _article(
        title="You won't believe this shocking AI agent!!!",
        content="agents " * 50,
        published=now,
    )
    breakdown = scoring_engine.score_article(article, now=now)
    assert "clickbait" in breakdown.penalties


# --- duplicate detection --- #
def test_duplicate_detection_same_url_and_title() -> None:
    a = _article(title="OpenAI launches agent SDK", url="https://x.com/1", overall=80)
    b = _article(title="OpenAI launches agent SDK!", url="https://x.com/2", overall=60)  # similar title
    c = _article(title="Totally unrelated QA story", url="https://x.com/3", overall=50)

    groups = duplicate_detector.group_stories([a, b, c])
    merged = duplicate_detector.assign_canonical_ids(groups)

    assert len(groups) == 2  # a+b merged, c separate
    assert merged == 1
    # Higher-scoring article (a) is canonical for its group.
    assert a.canonical_story_id == a.id == b.canonical_story_id


# --- ranking --- #
def test_ranking_engine_orders_and_positions() -> None:
    low = _article(url="https://x.com/low", overall=30)
    high = _article(url="https://x.com/high", overall=90)
    mid = _article(url="https://x.com/mid", overall=60)

    ranked = ranking_engine.rank_articles([low, high, mid])
    assert [a.overall_relevance_score for a in ranked] == [90, 60, 30]
    assert ranked[0].ranking_position == 1
    assert ranked[-1].ranking_position == 3


# --- selection --- #
def test_selection_rules_respect_quota() -> None:
    arts = []
    for i in range(8):  # 8 strong "stories"
        arts.append(_article(url=f"https://x.com/s{i}", overall=90 - i,
                             section=NewsletterSection.AGENTIC_AI_ENGINEERING))
    for i in range(5):  # 5 tools
        arts.append(_article(url=f"https://x.com/t{i}", overall=50 - i,
                             section=NewsletterSection.AI_TOOLS_WATCH))
    arts.append(_article(url="https://x.com/r", overall=40,
                         section=NewsletterSection.RESEARCH_WATCH))

    ranked = ranking_engine.rank_articles(arts)
    result = select_articles(ranked)

    sections = [a.newsletter_section for a in result.selected]
    assert sections.count(NewsletterSection.AGENTIC_AI_ENGINEERING) <= 5
    assert sections.count(NewsletterSection.AI_TOOLS_WATCH) <= 3
    assert NewsletterSection.RESEARCH_WATCH in sections
    assert all(a.is_selected for a in result.selected)
    # No duplicate stories selected.
    story_ids = [a.canonical_story_id or a.id for a in result.selected]
    assert len(story_ids) == len(set(story_ids))


def test_no_duplicate_story_selected() -> None:
    story = uuid.uuid4()
    a = _article(url="https://x.com/a", overall=90, section=NewsletterSection.AGENTIC_AI_ENGINEERING)
    b = _article(url="https://x.com/b", overall=85, section=NewsletterSection.AGENTIC_AI_ENGINEERING)
    a.canonical_story_id = story
    b.canonical_story_id = story  # same story

    result = select_articles(ranking_engine.rank_articles([a, b]))
    assert len(result.selected) == 1


# --- agent / DB persistence --- #
async def test_filter_agent_persists_and_selects(session_factory) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as s:
        src = _source(SourceType.DOCUMENTATION, credibility=0.95)
        s.add(src)
        await s.flush()
        for i in range(3):
            s.add(
                CollectedArticle(
                    source_id=src.id,
                    title=f"AI agent orchestration evaluation story {i}",
                    url=f"https://ex.com/story-{i}",
                    raw_content="agents orchestration architecture evaluation enterprise " * 10,
                    status=ArticleStatus.NEW,
                    credibility_score=0.95,
                    published_date=now,
                    newsletter_section=NewsletterSection.AGENTIC_AI_ENGINEERING,
                )
            )
        await s.commit()

    agent = RelevanceFilterAgent(session_factory)
    result = await agent.run()

    assert result["stats"]["scored"] == 3
    assert len(result["selected_article_ids"]) >= 1

    async with session_factory() as s:
        scored = await s.scalar(
            select(func.count())
            .select_from(CollectedArticle)
            .where(CollectedArticle.overall_relevance_score.is_not(None))
        )
        selected = await s.scalar(
            select(func.count())
            .select_from(CollectedArticle)
            .where(CollectedArticle.is_selected.is_(True))
        )
    assert scored == 3
    assert selected >= 1


async def test_filter_agent_empty(session_factory) -> None:
    agent = RelevanceFilterAgent(session_factory)
    result = await agent.run([])
    assert result["selected_article_ids"] == []
    assert result["stats"]["scored"] == 0


def test_update_workflow_state() -> None:
    agent = RelevanceFilterAgent(lambda: None)  # no DB needed
    update = agent.update_workflow_state({}, ["a", "b"], {"X": ["a"]})
    assert update == {"selected_article_ids": ["a", "b"], "category_map": {"X": ["a"]}}
