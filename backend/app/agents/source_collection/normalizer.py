"""Normalization layer.

Cleans whitespace/encodings, canonicalizes URLs, parses dates, computes a stable
content hash, and projects source-strategy hints onto an article dict ready for
persistence.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.agents.source_collection.types import RawArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod

_WS_RE = re.compile(r"\s+")
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref")


def normalize_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    return _WS_RE.sub(" ", text).strip() or None


def normalize_title(title: str | None) -> str:
    return normalize_whitespace(title) or "Untitled"


def normalize_url(url: str) -> str:
    """Canonicalize a URL: lowercase scheme/host, drop fragments and trackers."""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query_parts = [pair for pair in parsed.query.split("&") if pair and not pair.lower().startswith(_TRACKING_PREFIXES)]
    query = "&".join(query_parts)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_date(value: Any) -> datetime | None:
    """Coerce various date representations to a timezone-aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # feedparser time.struct_time
    if hasattr(value, "tm_year"):
        import time as _time

        return datetime.fromtimestamp(_time.mktime(value), tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        for fmt in (None, "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d"):
            try:
                dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def compute_content_hash(title: str, url: str, content: str | None) -> str:
    """Stable SHA-256 over canonical title + url + a content prefix."""
    basis = "|".join(
        [
            normalize_title(title).lower(),
            normalize_url(url),
            (normalize_whitespace(content) or "")[:500].lower(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def compute_freshness(published: datetime | None) -> float:
    if published is None:
        return 0.5
    age_days = (datetime.now(timezone.utc) - published).days
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.7
    if age_days <= 90:
        return 0.4
    return 0.2


def normalize_article(
    raw: RawArticle,
    source: ContentSource,
    collection_method: CollectionMethod | str,
) -> dict[str, Any]:
    """Build a persistence-ready dict from a raw article + its source."""
    title = normalize_title(raw.title)
    url = normalize_url(raw.url)
    content = normalize_whitespace(raw.raw_content)
    summary = normalize_whitespace(raw.summary)
    published = normalize_date(raw.published_date)

    return {
        "source_id": source.id,
        "title": title,
        "url": url,
        "author": normalize_whitespace(raw.author),
        "published_date": published,
        "raw_content": content,
        "summary": summary,
        "status": ArticleStatus.NEW,
        "content_hash": compute_content_hash(title, url, content),
        "source_priority": source.priority,
        "source_category": source.category,
        "newsletter_section": source.newsletter_section,
        "collection_method": CollectionMethod(collection_method),
        "credibility_score": source.credibility_score,
        "freshness_score": compute_freshness(published),
        "relevance_hint": source.best_use,
    }
