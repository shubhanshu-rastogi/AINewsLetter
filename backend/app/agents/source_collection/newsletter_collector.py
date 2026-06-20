"""Newsletter / trend-signal collector.

Prefers an RSS feed when available; otherwise falls back to collecting the
public homepage. Only publicly available content is collected - no paywalled or
subscriber-only content is accessed.
"""

from __future__ import annotations

from app.agents.source_collection.rss_collector import collect_rss
from app.agents.source_collection.types import RawArticle
from app.agents.source_collection.web_collector import collect_website
from app.core.config import settings
from app.core.logging import get_logger
from app.models.content_source import ContentSource

logger = get_logger("collection.newsletter")


async def collect_newsletter_source(source: ContentSource) -> list[RawArticle]:
    if source.rss_url:
        articles = await collect_rss(source, limit=settings.NEWSLETTER_BATCH_SIZE)
    else:
        articles = await collect_website(source)
    logger.info("trend_source_collected", source=source.source_name, count=len(articles))
    return articles
