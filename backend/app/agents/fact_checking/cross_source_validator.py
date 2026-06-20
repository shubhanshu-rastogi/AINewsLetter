"""Claim extraction + cross-source validation.

Claims are extracted heuristically (numbers, benchmark/launch/release/eval
signals). Validation cross-checks each claim against the article's own source
trust and corroboration from *other* sources in the corpus.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.enums import ClaimType, ClaimVerification, TrustTier

logger = get_logger("factcheck.crosssource")

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_NUMBER_RE = re.compile(r"\d")
_PERCENT_RE = re.compile(r"\d+(\.\d+)?\s?%")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "this",
    "that",
    "from",
    "by",
    "at",
    "as",
    "it",
}
_NEGATIONS = ("not ", "no ", "false", "debunk", "myth", "incorrect", "denies")


@dataclass(slots=True)
class Claim:
    text: str
    claim_type: ClaimType


@dataclass(slots=True)
class ClaimResult:
    claim_text: str
    claim_type: ClaimType
    status: ClaimVerification
    support_score: float
    corroborating_sources: int


def _classify_claim(sentence: str) -> ClaimType | None:
    s = sentence.lower()
    if _PERCENT_RE.search(sentence):
        return ClaimType.STATISTIC
    if any(k in s for k in ("benchmark", "swe-bench", "pass@", "outperform", "state-of-the-art", "leaderboard")):
        return ClaimType.BENCHMARK
    if any(k in s for k in ("launch", "introducing", "available now", "unveil")):
        return ClaimType.PRODUCT_LAUNCH
    if any(k in s for k in ("release", "version ", "now generally available", "ga ")):
        return ClaimType.RELEASE
    if any(k in s for k in ("evaluation", "eval ", "rubric", "accuracy", "f1", "score")):
        return ClaimType.EVALUATION
    if _NUMBER_RE.search(sentence):
        return ClaimType.METRIC
    if len(sentence) >= 40:
        return ClaimType.FACT
    return None


def extract_claims(text: str, *, limit: int | None = None) -> list[Claim]:
    limit = limit or settings.MAX_CLAIMS_PER_ARTICLE
    claims: list[Claim] = []
    seen: set[str] = set()
    for sentence in _SENTENCE_RE.split(text or ""):
        sentence = sentence.strip()
        if len(sentence) < 20 or sentence.lower() in seen:
            continue
        claim_type = _classify_claim(sentence)
        if claim_type is None:
            continue
        seen.add(sentence.lower())
        claims.append(Claim(text=sentence[:500], claim_type=claim_type))
        if len(claims) >= limit:
            break
    logger.info("claims_extracted", count=len(claims))
    return claims


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _corroborators(claim: Claim, article: CollectedArticle, corpus: Sequence[CollectedArticle]):
    claim_kw = _keywords(claim.text)
    count = 0
    contradicted = False
    for other in corpus:
        if other.id == article.id or other.source_id == article.source_id:
            continue
        other_text = f"{other.title or ''} {other.summary or ''} {(other.raw_content or '')[:2000]}".lower()
        shared = claim_kw & _keywords(other_text)
        if len(shared) >= 2:
            count += 1
            if any(neg in other_text for neg in _NEGATIONS):
                contradicted = True
    return count, contradicted


def validate_claim(
    claim: Claim,
    article: CollectedArticle,
    tier: TrustTier,
    corpus: Sequence[CollectedArticle],
) -> ClaimResult:
    corroborators, contradicted = _corroborators(claim, article, corpus)

    if contradicted:
        status, score = ClaimVerification.CONTRADICTED, 10.0
    elif tier == TrustTier.HIGH:
        status = ClaimVerification.SUPPORTED
        score = min(100.0, 85.0 + corroborators * 5)
    elif corroborators >= 2:
        status, score = ClaimVerification.SUPPORTED, 80.0
    elif corroborators == 1 or tier == TrustTier.MEDIUM:
        status, score = ClaimVerification.PARTIALLY_SUPPORTED, 60.0
    else:
        status, score = ClaimVerification.UNVERIFIED, 30.0

    return ClaimResult(
        claim_text=claim.text,
        claim_type=claim.claim_type,
        status=status,
        support_score=round(score, 2),
        corroborating_sources=corroborators,
    )


def validate_claims(
    claims: Sequence[Claim],
    article: CollectedArticle,
    tier: TrustTier,
    corpus: Sequence[CollectedArticle],
) -> list[ClaimResult]:
    results = [validate_claim(c, article, tier, corpus) for c in claims]
    logger.info("cross_source_validation_completed", claims=len(results))
    return results
