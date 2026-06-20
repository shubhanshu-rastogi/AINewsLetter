"""Confidence scoring + publication-status thresholds."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.agents.fact_checking.cross_source_validator import ClaimResult
from app.core.logging import get_logger
from app.models.enums import ClaimVerification, VerificationStatus

logger = get_logger("factcheck.confidence")

_WEIGHTS = {
    "source_credibility": 0.30,
    "claim_verification": 0.30,
    "cross_source": 0.15,
    "freshness": 0.10,
    "evidence": 0.15,
}


@dataclass(slots=True)
class ConfidenceResult:
    source_credibility_score: float
    claim_verification_score: float
    cross_source_score: float
    freshness_score: float
    evidence_score: float
    overall_confidence_score: float
    verification_status: VerificationStatus


def _clamp(v: float) -> float:
    return round(max(0.0, min(100.0, v)), 2)


def status_for(score: float) -> VerificationStatus:
    if score >= 90:
        return VerificationStatus.VERIFIED
    if score >= 70:
        return VerificationStatus.REVIEW_REQUIRED
    if score >= 50:
        return VerificationStatus.LOW_CONFIDENCE
    return VerificationStatus.REJECTED


def compute_confidence(
    *,
    source_credibility: float,
    claim_results: Sequence[ClaimResult],
    url_accessible: bool,
    freshness: float,
    citations_count: int,
) -> ConfidenceResult:
    if claim_results:
        claim_verification = sum(c.support_score for c in claim_results) / len(claim_results)
        supported = sum(
            1 for c in claim_results if c.status in (ClaimVerification.SUPPORTED, ClaimVerification.PARTIALLY_SUPPORTED)
        )
        with_corroboration = sum(1 for c in claim_results if c.corroborating_sources > 0)
        supported_fraction = supported / len(claim_results)
        cross_source = (with_corroboration / len(claim_results)) * 100
    else:
        # No extractable claims: lean on source credibility, but cap evidence.
        claim_verification = source_credibility * 0.6
        supported_fraction = 0.0
        cross_source = 0.0

    evidence = _clamp(citations_count * 15 + supported_fraction * 40 + (20 if url_accessible else 0))

    overall = _clamp(
        _WEIGHTS["source_credibility"] * source_credibility
        + _WEIGHTS["claim_verification"] * _clamp(claim_verification)
        + _WEIGHTS["cross_source"] * _clamp(cross_source)
        + _WEIGHTS["freshness"] * _clamp(freshness)
        + _WEIGHTS["evidence"] * evidence
    )
    result = ConfidenceResult(
        source_credibility_score=_clamp(source_credibility),
        claim_verification_score=_clamp(claim_verification),
        cross_source_score=_clamp(cross_source),
        freshness_score=_clamp(freshness),
        evidence_score=evidence,
        overall_confidence_score=overall,
        verification_status=status_for(overall),
    )
    logger.info(
        "confidence_score_generated",
        overall=overall,
        status=result.verification_status,
    )
    return result
