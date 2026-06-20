"""Deterministic relevance scoring engine.

Each dimension is scored 0-100 from article + source signals and keyword
heuristics, then combined into an ``overall_relevance_score`` with penalties
for clickbait / promotional / low-signal / stale content.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.agents import taxonomy
from app.models.collected_article import CollectedArticle
from app.models.enums import SourceType

STALE_DAYS = 14

# Weights for the overall score (sum = 1.0).
_WEIGHTS = {
    "newsletter_relevance": 0.30,
    "credibility": 0.20,
    "freshness": 0.15,
    "technical_depth": 0.15,
    "enterprise_value": 0.07,
    "qa_value": 0.07,
    "trend_signal": 0.06,
}


@dataclass(slots=True)
class ScoreBreakdown:
    credibility_score: float
    freshness_score: float
    newsletter_relevance_score: float
    technical_depth_score: float
    enterprise_value_score: float
    qa_value_score: float
    trend_signal_score: float
    overall_relevance_score: float
    penalties: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def _article_text(article: CollectedArticle) -> str:
    parts = [article.title or "", article.summary or "", (article.raw_content or "")[:5000]]
    return " ".join(parts).lower()


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def credibility_dimension(article: CollectedArticle) -> float:
    base = (article.credibility_score or 0.5) * 100
    return _clamp(base)


def freshness_dimension(published: datetime | None, *, now: datetime | None = None) -> float:
    if published is None:
        return 50.0
    now = now or datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_days = (now - published).days
    if age_days <= 1:
        return 100.0
    if age_days <= 7:
        return _clamp(100 - age_days * 5)  # 7d -> 65
    if age_days <= STALE_DAYS:
        return _clamp(65 - (age_days - 7) * 5)  # 14d -> 30
    return _clamp(30 - (age_days - STALE_DAYS) * 5)  # steep penalty past 14d


def newsletter_relevance_dimension(text: str) -> float:
    total_hits = sum(taxonomy.count_hits(text, kws) for kws in taxonomy.SECTION_KEYWORDS.values())
    return _clamp(40 + total_hits * 8)


def technical_depth_dimension(text: str, content_len: int) -> float:
    hits = taxonomy.count_hits(text, taxonomy.TECHNICAL_KEYWORDS)
    length_bonus = min(content_len / 50, 40)  # up to +40 for long, substantive content
    return _clamp(20 + hits * 8 + length_bonus)


def enterprise_dimension(text: str) -> float:
    return _clamp(taxonomy.count_hits(text, taxonomy.ENTERPRISE_KEYWORDS) * 20)


def qa_dimension(text: str) -> float:
    return _clamp(taxonomy.count_hits(text, taxonomy.QA_KEYWORDS) * 18)


def trend_dimension(article: CollectedArticle, text: str) -> float:
    hits = taxonomy.count_hits(text, taxonomy.TREND_KEYWORDS)
    source_bonus = 0.0
    st = article.source.source_type if article.source else None
    if st in (SourceType.TREND_SIGNAL, SourceType.NEWSLETTER):
        source_bonus = 20.0
    return _clamp(hits * 15 + source_bonus)


def _penalties(article: CollectedArticle, text: str, freshness: float) -> tuple[float, list[str]]:
    multiplier = 1.0
    reasons: list[str] = []
    if any(p in text for p in taxonomy.CLICKBAIT_PATTERNS):
        multiplier *= 0.7
        reasons.append("clickbait")
    if any(p in text for p in taxonomy.PROMO_PATTERNS):
        multiplier *= 0.6
        reasons.append("promotional")
    content_len = len(article.raw_content or "")
    if content_len < 200:
        multiplier *= 0.85
        reasons.append("low_signal")
    if freshness <= 30 and article.published_date is not None:
        multiplier *= 0.8
        reasons.append("stale")
    return multiplier, reasons


def score_article(article: CollectedArticle, *, now: datetime | None = None) -> ScoreBreakdown:
    text = _article_text(article)
    content_len = len(article.raw_content or "")

    credibility = credibility_dimension(article)
    freshness = freshness_dimension(article.published_date, now=now)
    relevance = newsletter_relevance_dimension(text)
    depth = technical_depth_dimension(text, content_len)
    enterprise = enterprise_dimension(text)
    qa = qa_dimension(text)
    trend = trend_dimension(article, text)

    weighted = (
        _WEIGHTS["newsletter_relevance"] * relevance
        + _WEIGHTS["credibility"] * credibility
        + _WEIGHTS["freshness"] * freshness
        + _WEIGHTS["technical_depth"] * depth
        + _WEIGHTS["enterprise_value"] * enterprise
        + _WEIGHTS["qa_value"] * qa
        + _WEIGHTS["trend_signal"] * trend
    )
    multiplier, reasons = _penalties(article, text, freshness)
    overall = _clamp(weighted * multiplier)

    return ScoreBreakdown(
        credibility_score=credibility,
        freshness_score=freshness,
        newsletter_relevance_score=relevance,
        technical_depth_score=depth,
        enterprise_value_score=enterprise,
        qa_value_score=qa,
        trend_signal_score=trend,
        overall_relevance_score=overall,
        penalties=reasons,
    )
