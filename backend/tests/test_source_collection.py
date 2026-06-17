"""Source Collection Agent tests (all external requests are mocked)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.agents.source_collection import (
    deduplicator,
    documentation_collector,
    normalizer,
    research_collector,
    rss_collector,
    source_strategy,
    web_collector,
)
from app.agents.source_collection.collector import SourceCollectionAgent
from app.agents.source_collection.exceptions import FetchError
from app.agents.source_collection.types import RawArticle
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import (
    ArticleStatus,
    CollectionMethod,
    NewsletterSection,
    SourceType,
)

# --------------------------------------------------------------------------- #
# Canned external payloads
# --------------------------------------------------------------------------- #
RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>Agent One</title><link>https://ex.com/a1</link>
<author>Jane Doe</author><pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
<description>Snippet one</description></item>
<item><title>Agent Two</title><link>https://ex.com/a2</link>
<description>Snippet two</description></item>
</channel></rss>""".encode()

HTML_PAGE = """<html><head><title>Doc Title</title>
<meta name="description" content="A description."></head>
<body><article>Main body content here.</article></body></html>"""

ARXIV_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Paper A</title><id>http://arxiv.org/abs/2401.0001</id>
<link href="http://arxiv.org/abs/2401.0001"/>
<published>2024-01-01T00:00:00Z</published>
<summary>Abstract of paper A.</summary>
<author><name>Alice</name></author></entry>
</feed>""".encode()


def _source(**overrides) -> ContentSource:
    """A transient ContentSource with all strategy fields explicitly set."""
    defaults = dict(
        id=uuid.uuid4(),
        source_name="Example",
        source_type=SourceType.RSS,
        source_url="https://ex.com",
        rss_url="https://ex.com/feed",
        category="Agentic AI Engineering",
        best_use="testing",
        priority=1,
        credibility_score=0.9,
        freshness_score=0.8,
        relevance_score=0.85,
        preferred_collection_method=CollectionMethod.RSS,
        fallback_collection_method=CollectionMethod.WEB,
        newsletter_section=NewsletterSection.AGENTIC_AI_ENGINEERING,
    )
    defaults.update(overrides)
    return ContentSource(**defaults)


# --------------------------------------------------------------------------- #
# Collectors
# --------------------------------------------------------------------------- #
async def test_rss_parsing(monkeypatch) -> None:
    async def fake_fetch(url, **kw):
        return RSS_XML

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    articles = await rss_collector.collect_rss(_source())

    assert len(articles) == 2
    assert articles[0].title == "Agent One"
    assert articles[0].url == "https://ex.com/a1"
    assert articles[0].author == "Jane Doe"
    assert articles[0].published_date is not None


async def test_website_collection(monkeypatch) -> None:
    async def fake_text(url, **kw):
        return HTML_PAGE

    async def fake_robots(url):
        return True

    monkeypatch.setattr(web_collector, "fetch_text", fake_text)
    monkeypatch.setattr(web_collector, "is_allowed_by_robots", fake_robots)

    articles = await web_collector.collect_website(_source(source_type=SourceType.WEBSITE))
    assert len(articles) == 1
    assert articles[0].title == "Doc Title"
    assert "Main body content" in articles[0].raw_content
    assert articles[0].summary == "A description."


async def test_documentation_collection(monkeypatch) -> None:
    async def fake_text(url, **kw):
        return HTML_PAGE

    async def fake_robots(url):
        return True

    monkeypatch.setattr(documentation_collector, "fetch_text", fake_text)
    monkeypatch.setattr(documentation_collector, "is_allowed_by_robots", fake_robots)

    articles = await documentation_collector.collect_documentation(
        _source(source_type=SourceType.DOCUMENTATION)
    )
    assert len(articles) == 1
    assert articles[0].title == "Doc Title"


async def test_research_collection(monkeypatch) -> None:
    async def fake_fetch(url, **kw):
        return ARXIV_ATOM

    monkeypatch.setattr(research_collector, "fetch_bytes", fake_fetch)
    articles = await research_collector.collect_research(
        _source(source_type=SourceType.RESEARCH)
    )
    assert len(articles) == 1
    assert articles[0].title == "Paper A"
    assert articles[0].author == "Alice"
    assert articles[0].raw_content == "Abstract of paper A."  # abstract as raw_content


async def test_newsletter_source_collection(monkeypatch) -> None:
    async def fake_fetch(url, **kw):
        return RSS_XML

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    from app.agents.source_collection import newsletter_collector

    articles = await newsletter_collector.collect_newsletter_source(
        _source(source_type=SourceType.NEWSLETTER)
    )
    assert len(articles) == 2  # used RSS path


# --------------------------------------------------------------------------- #
# Strategy / normalization / dedup
# --------------------------------------------------------------------------- #
def test_source_strategy_scoring() -> None:
    high = _source(priority=1, credibility_score=0.9, relevance_score=0.9, freshness_score=0.9)
    low = _source(priority=5, credibility_score=0.5, relevance_score=0.5, freshness_score=0.5)

    ordered = source_strategy.order_sources([low, high])
    assert ordered[0] is high  # priority 1 first

    assert source_strategy.composite_score(high) > source_strategy.composite_score(low)
    view = source_strategy.strategy_view(high)
    assert view["preferred_collection_method"] == CollectionMethod.RSS
    assert "composite_score" in view


def test_normalization() -> None:
    assert normalizer.normalize_whitespace("  a\n b ") == "a b"
    assert normalizer.normalize_url("HTTPS://Ex.com/Path/?utm_source=x&q=1#frag") == (
        "https://ex.com/Path?q=1"
    )

    dt = normalizer.normalize_date("2024-01-01")
    assert dt is not None and dt.tzinfo is not None

    h1 = normalizer.compute_content_hash("Title", "https://ex.com/a", "body")
    h2 = normalizer.compute_content_hash("Title", "https://ex.com/a", "body")
    assert h1 == h2 and len(h1) == 64

    raw = RawArticle(title=" Hello ", url="https://ex.com/x?utm_source=y", raw_content="c")
    normalized = normalizer.normalize_article(raw, _source(), CollectionMethod.RSS)
    assert normalized["title"] == "Hello"
    assert normalized["status"] == ArticleStatus.NEW
    assert normalized["content_hash"]


async def test_deduplication(session) -> None:
    source = _source()
    session.add(source)
    await session.flush()

    article = CollectedArticle(
        source_id=source.id,
        title="Existing Title",
        url="https://ex.com/existing",
        content_hash="hash-123",
        status=ArticleStatus.NEW,
    )
    session.add(article)
    await session.flush()

    # Same URL
    dup, reason = await deduplicator.find_duplicate(
        session, {"url": "https://ex.com/existing", "content_hash": "x", "title": "T"}
    )
    assert dup and reason == "same_url"

    # Same content hash
    dup, reason = await deduplicator.find_duplicate(
        session, {"url": "https://ex.com/other", "content_hash": "hash-123", "title": "T"}
    )
    assert dup and reason == "same_content_hash"

    # Similar title within batch
    dup, reason = await deduplicator.find_duplicate(
        session,
        {"url": "https://ex.com/new", "content_hash": "z", "title": "Breaking AI news today"},
        batch_titles=["Breaking AI news today!"],
    )
    assert dup and reason == "similar_title"

    # Unique
    dup, reason = await deduplicator.find_duplicate(
        session, {"url": "https://ex.com/unique", "content_hash": "q", "title": "Totally different"}
    )
    assert not dup and reason is None


# --------------------------------------------------------------------------- #
# Persistence + agent + error handling
# --------------------------------------------------------------------------- #
async def test_database_persistence(session_factory, monkeypatch) -> None:
    async def fake_fetch(url, **kw):
        return RSS_XML

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)

    async with session_factory() as s:
        source = _source()
        s.add(source)
        await s.commit()
        source_id = source.id

    agent = SourceCollectionAgent(session_factory)
    result = await agent.collect_source(source_id)

    assert result.failed is False
    assert result.new == 2
    assert len(result.article_ids) == 2

    async with session_factory() as s:
        from sqlalchemy import func, select

        count = await s.scalar(select(func.count()).select_from(CollectedArticle))
    assert count == 2


async def test_error_handling(session_factory, monkeypatch) -> None:
    async def boom(url, **kw):
        raise FetchError("network down")

    monkeypatch.setattr(rss_collector, "fetch_bytes", boom)

    async with session_factory() as s:
        # No fallback so the failure is surfaced as a failed result (not a crash).
        source = _source(fallback_collection_method=None)
        s.add(source)
        await s.commit()
        source_id = source.id

    agent = SourceCollectionAgent(session_factory)
    result = await agent.collect_source(source_id)
    assert result.failed is True
    assert "network down" in (result.error or "")


# --------------------------------------------------------------------------- #
# Scheduler + workflow integration
# --------------------------------------------------------------------------- #
async def test_scheduler_startup() -> None:
    from app.agents.source_collection.scheduler import CollectionScheduler

    sched = CollectionScheduler()
    sched.start()
    try:
        assert sched.running is True
        jobs = sched._scheduler.get_jobs()  # noqa: SLF001 - test introspection
        assert len(jobs) == 2
    finally:
        sched.shutdown()
    assert sched.running is False


async def test_workflow_integration(workflow_service, monkeypatch) -> None:
    async def fake_fetch(url, **kw):
        return RSS_XML

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)

    # Seed one active RSS source into the workflow's database.
    async with workflow_service.session_factory() as s:
        s.add(_source())
        await s.commit()

    result = await workflow_service.start_newsletter_workflow()
    state = result["state"]
    assert len(state["collected_article_ids"]) == 2  # collected via the node->agent path
    assert state["current_step"] == "human_review_node"
