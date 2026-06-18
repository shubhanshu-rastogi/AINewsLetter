"""Source verification: URL accessibility, trust tier, credibility, date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.enums import SourceType, TrustTier

logger = get_logger("factcheck.source")

# Domain -> trust tier (substring match on netloc).
HIGH_TRUST_DOMAINS = [
    "openai.com", "anthropic.com", "google.com", "cloud.google.com",
    "microsoft.com", "learn.microsoft.com", "aws.amazon.com", "amazon.com",
    "arxiv.org", "thoughtworks.com", "ministryoftesting.com", "infoq.com",
    "deeplearning.ai", "adk.dev", "swebench.com",
]
MEDIUM_TRUST_DOMAINS = ["tldr.tech", "bensbites.com", "latent.space"]

# Source-type fallback when the domain is unknown.
_TYPE_TIER: dict[SourceType, tuple[TrustTier, float]] = {
    SourceType.DOCUMENTATION: (TrustTier.HIGH, 90.0),
    SourceType.RESEARCH: (TrustTier.HIGH, 90.0),
    SourceType.BENCHMARK: (TrustTier.HIGH, 88.0),
    SourceType.ENTERPRISE_REPORT: (TrustTier.HIGH, 85.0),
    SourceType.RSS: (TrustTier.MEDIUM, 72.0),
    SourceType.BLOG: (TrustTier.MEDIUM, 68.0),
    SourceType.NEWSLETTER: (TrustTier.MEDIUM, 68.0),
    SourceType.TREND_SIGNAL: (TrustTier.MEDIUM, 64.0),
    SourceType.WEBSITE: (TrustTier.MEDIUM, 60.0),
}
_TIER_SCORE = {TrustTier.HIGH: 95.0, TrustTier.MEDIUM: 70.0, TrustTier.LOW: 40.0}


@dataclass(slots=True)
class UrlCheck:
    accessible: bool
    status_code: int | None = None
    skipped: bool = False


def _domain(article: CollectedArticle) -> str:
    url = article.url or (article.source.source_url if article.source else "")
    return urlparse(url).netloc.lower()


def verify_source(article: CollectedArticle) -> tuple[TrustTier, float]:
    """Return (trust tier, credibility score 0-100)."""
    domain = _domain(article)
    if any(d in domain for d in HIGH_TRUST_DOMAINS):
        return TrustTier.HIGH, _TIER_SCORE[TrustTier.HIGH]
    if any(d in domain for d in MEDIUM_TRUST_DOMAINS):
        return TrustTier.MEDIUM, _TIER_SCORE[TrustTier.MEDIUM]
    source_type = article.source.source_type if article.source else None
    if source_type in _TYPE_TIER:
        return _TYPE_TIER[source_type]
    return TrustTier.LOW, _TIER_SCORE[TrustTier.LOW]


def verify_date(published: datetime | None) -> bool:
    """A publication date is valid if present and not in the future."""
    if published is None:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published <= datetime.now(timezone.utc) + timedelta(days=1)


async def _http_head(url: str) -> tuple[bool, int | None]:
    async with httpx.AsyncClient(timeout=settings.COLLECTION_TIMEOUT, follow_redirects=True) as client:
        response = await client.head(url)
        return response.status_code < 400, response.status_code


async def verify_url(url: str) -> UrlCheck:
    """Check URL accessibility (skipped when FACT_CHECK_VERIFY_URLS is off)."""
    if not settings.FACT_CHECK_VERIFY_URLS:
        return UrlCheck(accessible=True, skipped=True)
    try:
        ok, code = await _http_head(url)
        logger.info("source_verified", url=url, status_code=code, accessible=ok)
        return UrlCheck(accessible=ok, status_code=code)
    except Exception as exc:  # noqa: BLE001 - inaccessibility is data, not a crash
        logger.warning("source_verify_failed", url=url, error=str(exc))
        return UrlCheck(accessible=False)
