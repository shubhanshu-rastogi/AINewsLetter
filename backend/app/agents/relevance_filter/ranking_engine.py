"""Ranking engine.

Orders canonical articles by overall score, freshness, credibility, and a small
per-section importance bonus, then assigns ``ranking_position`` (1..N, capped 100).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection as NS

# Editorial importance bonus per section (small tie-breaker influence).
SECTION_IMPORTANCE: dict[NS, float] = {
    NS.AGENTIC_AI_ENGINEERING: 5.0,
    NS.AI_EVALUATION_QA_GATES: 4.0,
    NS.AI_TESTING_QUALITY: 4.0,
    NS.ENTERPRISE_AI_ADOPTION: 3.0,
    NS.CODING_AGENT_BENCHMARK: 3.0,
    NS.RESEARCH_WATCH: 2.0,
    NS.AI_TOOLS_WATCH: 2.0,
    NS.WEEKLY_TREND_SIGNALS: 1.0,
}


def _rank_key(article: CollectedArticle) -> float:
    section = article.newsletter_section
    importance = SECTION_IMPORTANCE.get(section, 0.0) if section else 0.0
    return (
        (article.overall_relevance_score or 0.0)
        + 0.1 * (article.freshness_score or 0.0)
        + 0.05 * (article.credibility_score or 0.0)
        + importance
    )


def rank_articles(articles: Sequence[CollectedArticle]) -> list[CollectedArticle]:
    """Return articles sorted best-first with ``ranking_position`` assigned."""
    ranked = sorted(articles, key=_rank_key, reverse=True)
    for position, article in enumerate(ranked, start=1):
        article.ranking_position = min(position, 100)
    return ranked
