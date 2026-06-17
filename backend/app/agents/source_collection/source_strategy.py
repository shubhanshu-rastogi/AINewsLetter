"""Source strategy layer.

Maps source types to collection methods, computes a composite priority score,
and exposes a strategy view. Per-source scores live on the ``content_sources``
rows (seeded); this module is the logic that interprets and orders them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.logging import get_logger
from app.models.content_source import ContentSource
from app.models.enums import CollectionMethod, SourceType

logger = get_logger("collection.strategy")

# Default (preferred, fallback) collection method per source type.
_METHOD_MAP: dict[SourceType, tuple[CollectionMethod, CollectionMethod | None]] = {
    SourceType.RSS: (CollectionMethod.RSS, CollectionMethod.WEB),
    SourceType.BLOG: (CollectionMethod.RSS, CollectionMethod.WEB),
    SourceType.WEBSITE: (CollectionMethod.WEB, None),
    SourceType.DOCUMENTATION: (CollectionMethod.DOCUMENTATION, CollectionMethod.WEB),
    SourceType.RESEARCH: (CollectionMethod.RESEARCH, CollectionMethod.WEB),
    SourceType.BENCHMARK: (CollectionMethod.WEB, None),
    SourceType.NEWSLETTER: (CollectionMethod.NEWSLETTER, CollectionMethod.WEB),
    SourceType.TREND_SIGNAL: (CollectionMethod.NEWSLETTER, CollectionMethod.WEB),
    SourceType.ENTERPRISE_REPORT: (CollectionMethod.WEB, CollectionMethod.DOCUMENTATION),
}

# Weights for the composite score.
_W_CREDIBILITY = 0.4
_W_RELEVANCE = 0.4
_W_FRESHNESS = 0.2


def methods_for_type(
    source_type: SourceType | str,
) -> tuple[CollectionMethod, CollectionMethod | None]:
    st = SourceType(source_type)
    return _METHOD_MAP.get(st, (CollectionMethod.WEB, None))


def composite_score(source: ContentSource) -> float:
    """Weighted score in [0, 1] from credibility, relevance, and freshness."""
    return round(
        _W_CREDIBILITY * (source.credibility_score or 0.0)
        + _W_RELEVANCE * (source.relevance_score or 0.0)
        + _W_FRESHNESS * (source.freshness_score or 0.0),
        4,
    )


def order_sources(sources: Sequence[ContentSource]) -> list[ContentSource]:
    """Order by explicit priority (ascending = higher), then composite score."""
    ordered = sorted(
        sources,
        key=lambda s: (s.priority, -composite_score(s)),
    )
    logger.info("strategy_applied", source_count=len(ordered))
    return ordered


def strategy_view(source: ContentSource) -> dict[str, Any]:
    """Serializable strategy summary for a source (used by the API)."""
    preferred, fallback = methods_for_type(source.source_type)
    return {
        "source_id": str(source.id),
        "source_name": source.source_name,
        "source_type": source.source_type,
        "category": source.category,
        "priority": source.priority,
        "credibility_score": source.credibility_score,
        "freshness_score": source.freshness_score,
        "relevance_score": source.relevance_score,
        "composite_score": composite_score(source),
        "preferred_collection_method": source.preferred_collection_method or preferred,
        "fallback_collection_method": source.fallback_collection_method or fallback,
        "newsletter_section": source.newsletter_section,
    }
