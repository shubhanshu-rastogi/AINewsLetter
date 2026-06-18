"""Citation generation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle

logger = get_logger("factcheck.citation")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def build_citations(
    article: CollectedArticle, supporting: Sequence[CollectedArticle] = ()
) -> list[dict]:
    """Build citation dicts: the primary source plus any corroborating sources."""
    now = datetime.now(timezone.utc)
    citations: list[dict] = [
        {
            "title": article.title,
            "source_name": article.source.source_name if article.source else None,
            "source_url": article.url,
            "publication_date": _iso(article.published_date),
            "retrieval_timestamp": now.isoformat(),
        }
    ]
    seen = {article.url}
    for other in supporting:
        if other.url in seen:
            continue
        seen.add(other.url)
        citations.append(
            {
                "title": other.title,
                "source_name": other.source.source_name if other.source else None,
                "source_url": other.url,
                "publication_date": _iso(other.published_date),
                "retrieval_timestamp": now.isoformat(),
            }
        )
    logger.info("citations_generated", count=len(citations))
    return citations
