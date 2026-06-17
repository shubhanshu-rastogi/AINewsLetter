"""Deduplication service.

Duplicate rules:
  1. Same URL (already in DB)
  2. Same content hash (already in DB)
  3. Highly similar title (fuzzy, within the current batch or recent DB)
  4. Same story across sources (covered by 2 + 3)
"""

from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle

logger = get_logger("collection.dedup")

TITLE_SIMILARITY_THRESHOLD = 0.9


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_similar_title(title: str, known_titles: Iterable[str]) -> bool:
    return any(
        title_similarity(title, known) >= TITLE_SIMILARITY_THRESHOLD
        for known in known_titles
    )


async def find_duplicate(
    session: AsyncSession,
    normalized: dict,
    batch_titles: Iterable[str] = (),
) -> tuple[bool, str | None]:
    """Return ``(is_duplicate, reason)`` for a normalized article dict."""
    url = normalized["url"]
    content_hash = normalized.get("content_hash")
    title = normalized["title"]

    existing_url = await session.scalar(
        select(CollectedArticle.id).where(CollectedArticle.url == url)
    )
    if existing_url is not None:
        return True, "same_url"

    if content_hash:
        existing_hash = await session.scalar(
            select(CollectedArticle.id).where(
                CollectedArticle.content_hash == content_hash
            )
        )
        if existing_hash is not None:
            return True, "same_content_hash"

    if is_similar_title(title, batch_titles):
        return True, "similar_title"

    return False, None
