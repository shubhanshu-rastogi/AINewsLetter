"""Documentation collector.

Documentation pages are structured like generic web pages; we reuse the web
collector's parsing and just tag the citation/source URL. Kept as a distinct
module so doc-specific extraction can evolve independently.
"""

from __future__ import annotations

from app.agents.source_collection.exceptions import RobotsDisallowedError
from app.agents.source_collection.http_client import fetch_text, is_allowed_by_robots
from app.agents.source_collection.types import RawArticle
from app.agents.source_collection.web_collector import parse_page
from app.core.logging import get_logger
from app.models.content_source import ContentSource

logger = get_logger("collection.documentation")


async def collect_documentation(source: ContentSource) -> list[RawArticle]:
    url = source.source_url
    if not await is_allowed_by_robots(url):
        raise RobotsDisallowedError(f"robots.txt disallows {url}")
    html = await fetch_text(url)
    article = parse_page(html, url)
    logger.info("articles_collected", source=source.source_name, count=1, method="documentation")
    return [article]
