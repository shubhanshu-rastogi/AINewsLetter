"""Research collector for arXiv (cs.SE recent papers).

Uses the public arXiv Atom API and stores each paper's abstract as
``raw_content``. Only publicly available metadata/abstracts are collected.
"""

from __future__ import annotations

from urllib.parse import quote

import feedparser

from app.agents.source_collection.http_client import fetch_bytes
from app.agents.source_collection.types import RawArticle
from app.core.config import settings
from app.core.logging import get_logger
from app.models.content_source import ContentSource

logger = get_logger("collection.research")

_ARXIV_API = "http://export.arxiv.org/api/query"
_DEFAULT_QUERY = "cat:cs.SE"


def _build_api_url(query: str, limit: int) -> str:
    return (
        f"{_ARXIV_API}?search_query={quote(query)}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    )


async def collect_research(
    source: ContentSource, *, limit: int | None = None
) -> list[RawArticle]:
    limit = limit or settings.RESEARCH_BATCH_SIZE
    api_url = _build_api_url(_DEFAULT_QUERY, limit)

    content = await fetch_bytes(api_url)
    parsed = feedparser.parse(content)

    articles: list[RawArticle] = []
    for entry in parsed.entries[:limit]:
        authors = [a.get("name") for a in entry.get("authors", []) if a.get("name")]
        articles.append(
            RawArticle(
                title=entry.get("title", "Untitled"),
                url=entry.get("link") or entry.get("id", ""),
                author=", ".join(authors) or None,
                published_date=entry.get("published_parsed"),
                raw_content=entry.get("summary"),  # abstract stored as raw_content
                summary=entry.get("summary"),
                categories=[t.get("term") for t in entry.get("tags", []) if t.get("term")],
            )
        )

    logger.info(
        "research_source_collected", source=source.source_name, count=len(articles)
    )
    return articles
