"""Generic website collector.

Fetches a page, extracts the title, meta description, and main body text, and
returns a single :class:`RawArticle` representing the page. Respects robots.txt
(best effort).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.agents.source_collection.exceptions import RobotsDisallowedError
from app.agents.source_collection.http_client import fetch_text, is_allowed_by_robots
from app.agents.source_collection.types import RawArticle
from app.core.logging import get_logger
from app.models.content_source import ContentSource

logger = get_logger("collection.web")

_BODY_SELECTORS = ("article", "main", "[role=main]")
_MAX_BODY_CHARS = 20_000


def _extract_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"]
    if soup.title and soup.title.string:
        return soup.title.string
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Untitled"


def _extract_description(soup: BeautifulSoup) -> str | None:
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"]
    return None


def _extract_body(soup: BeautifulSoup) -> str:
    for selector in _BODY_SELECTORS:
        node = soup.select_one(selector)
        if node:
            return node.get_text(separator=" ", strip=True)[:_MAX_BODY_CHARS]
    body = soup.body or soup
    return body.get_text(separator=" ", strip=True)[:_MAX_BODY_CHARS]


def parse_page(html: str, url: str) -> RawArticle:
    soup = BeautifulSoup(html, "html.parser")
    return RawArticle(
        title=_extract_title(soup),
        url=url,
        published_date=None,
        raw_content=_extract_body(soup),
        summary=_extract_description(soup),
    )


async def collect_website(source: ContentSource) -> list[RawArticle]:
    url = source.source_url
    if not await is_allowed_by_robots(url):
        raise RobotsDisallowedError(f"robots.txt disallows {url}")
    html = await fetch_text(url)
    article = parse_page(html, url)
    logger.info("articles_collected", source=source.source_name, count=1, method="web")
    return [article]
