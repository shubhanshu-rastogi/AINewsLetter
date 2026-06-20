"""RSS / Atom feed collector."""

from __future__ import annotations

import feedparser

from app.agents.source_collection.http_client import fetch_bytes
from app.agents.source_collection.types import RawArticle
from app.core.config import settings
from app.core.logging import get_logger
from app.models.content_source import ContentSource

logger = get_logger("collection.rss")


def _entry_content(entry) -> str | None:
    if getattr(entry, "content", None):
        return entry.content[0].get("value")
    return entry.get("summary") or entry.get("description")


async def collect_rss(source: ContentSource, *, limit: int | None = None) -> list[RawArticle]:
    """Fetch and parse an RSS/Atom feed into raw articles."""
    feed_url = source.rss_url or source.source_url
    limit = limit or settings.RSS_BATCH_SIZE

    content = await fetch_bytes(feed_url)
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        logger.warning("rss_malformed", source=source.source_name, url=feed_url)

    articles: list[RawArticle] = []
    for entry in parsed.entries[:limit]:
        link = entry.get("link")
        if not link:
            continue
        articles.append(
            RawArticle(
                title=entry.get("title", "Untitled"),
                url=link,
                author=entry.get("author"),
                published_date=entry.get("published_parsed") or entry.get("updated_parsed"),
                raw_content=_entry_content(entry),
                summary=entry.get("summary"),
                categories=[t.get("term") for t in entry.get("tags", []) if t.get("term")],
            )
        )

    logger.info("articles_collected", source=source.source_name, count=len(articles), method="rss")
    return articles
