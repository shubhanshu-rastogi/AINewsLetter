"""Additional direct tests to exercise real (non-mocked-out) collection logic."""

from __future__ import annotations

import time
import uuid

import httpx
import pytest

from app.agents.source_collection import http_client, web_collector
from app.agents.source_collection.collector import SourceCollectionAgent
from app.agents.source_collection.exceptions import FetchError
from app.agents.source_collection.normalizer import compute_freshness, normalize_date
from app.agents.source_collection.source_seed import SOURCES, seed_sources
from app.models.content_source import ContentSource
from app.models.enums import CollectionMethod, NewsletterSection, SourceType

HTML_PAGE = "<html><head><title>T</title></head><body><article>Body</article></body></html>"


def _src(**kw) -> ContentSource:
    base = dict(
        id=uuid.uuid4(),
        source_name="S",
        source_type=SourceType.RSS,
        source_url="https://ex.com",
        rss_url="https://ex.com/feed",
        category="Agentic AI Engineering",
        best_use="x",
        priority=1,
        credibility_score=0.9,
        freshness_score=0.8,
        relevance_score=0.8,
        preferred_collection_method=CollectionMethod.RSS,
        fallback_collection_method=CollectionMethod.WEB,
        newsletter_section=NewsletterSection.AGENTIC_AI_ENGINEERING,
    )
    base.update(kw)
    return ContentSource(**base)


# --- seed (direct, so coverage sees it) --- #
async def test_seed_sources_direct(session) -> None:
    created = await seed_sources(session)
    assert created == len(SOURCES) == 15
    assert await seed_sources(session) == 0  # idempotent


# --- http client retry / failure / robots --- #
class _FakeResp:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    def __init__(self, script):
        self._script = script
        self._i = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        item = self._script[min(self._i, len(self._script) - 1)]
        self._i += 1
        if isinstance(item, Exception):
            raise item
        return item


def _patch_client(monkeypatch, script):
    # fetch_bytes constructs a new client per attempt; return one shared fake so
    # the response script advances across retries.
    client = _FakeClient(script)
    monkeypatch.setattr(http_client.httpx, "AsyncClient", lambda **kw: client)

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(http_client.asyncio, "sleep", _no_sleep)


async def test_fetch_retries_then_succeeds(monkeypatch) -> None:
    _patch_client(monkeypatch, [httpx.ConnectError("down"), _FakeResp(b"ok")])
    data = await http_client.fetch_bytes("https://ex.com", retries=3)
    assert data == b"ok"


async def test_fetch_fails_after_retries(monkeypatch) -> None:
    _patch_client(monkeypatch, [httpx.ConnectError("down")])
    with pytest.raises(FetchError):
        await http_client.fetch_bytes("https://ex.com", retries=2)


async def test_robots_allow_and_disallow(monkeypatch) -> None:
    robots = "User-agent: *\nDisallow: /private"

    async def fake_text(url, **kw):
        return robots

    monkeypatch.setattr(http_client, "fetch_text", fake_text)
    assert await http_client.is_allowed_by_robots("https://ex.com/public") is True
    assert await http_client.is_allowed_by_robots("https://ex.com/private/x") is False


async def test_robots_allows_when_unreachable(monkeypatch) -> None:
    async def boom(url, **kw):
        raise FetchError("no robots")

    monkeypatch.setattr(http_client, "fetch_text", boom)
    assert await http_client.is_allowed_by_robots("https://ex.com/x") is True


# --- web extraction branches --- #
def test_web_parse_og_title() -> None:
    html = (
        '<html><head><meta property="og:title" content="OG Title">'
        '<meta property="og:description" content="OG Desc"></head>'
        "<body><p>loose text</p></body></html>"
    )
    article = web_collector.parse_page(html, "https://ex.com")
    assert article.title == "OG Title"
    assert article.summary == "OG Desc"
    assert "loose text" in article.raw_content  # body fallback (no article/main)


def test_web_parse_h1_fallback() -> None:
    html = "<html><body><h1>Heading</h1><main>Main content</main></body></html>"
    article = web_collector.parse_page(html, "https://ex.com")
    assert article.title == "Heading"
    assert "Main content" in article.raw_content


# --- normalization extras --- #
def test_normalize_date_struct_time_and_none() -> None:
    assert normalize_date(None) is None
    st = time.gmtime(0)
    assert normalize_date(st) is not None


def test_compute_freshness_buckets() -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert compute_freshness(now) == 1.0
    assert compute_freshness(now - timedelta(days=20)) == 0.7
    assert compute_freshness(now - timedelta(days=200)) == 0.2
    assert compute_freshness(None) == 0.5


# --- collector fallback path --- #
async def test_collector_uses_fallback(session_factory, monkeypatch) -> None:
    from app.agents.source_collection import rss_collector
    from app.agents.source_collection import web_collector as wc

    async def rss_boom(url, **kw):
        raise FetchError("rss down")

    async def fake_text(url, **kw):
        return HTML_PAGE

    async def allow(url):
        return True

    monkeypatch.setattr(rss_collector, "fetch_bytes", rss_boom)
    monkeypatch.setattr(wc, "fetch_text", fake_text)
    monkeypatch.setattr(wc, "is_allowed_by_robots", allow)

    async with session_factory() as s:
        src = _src()  # preferred RSS, fallback WEB
        s.add(src)
        await s.commit()
        src_id = src.id

    agent = SourceCollectionAgent(session_factory)
    result = await agent.collect_source(src_id)
    assert result.failed is False
    assert result.new == 1  # collected via WEB fallback
