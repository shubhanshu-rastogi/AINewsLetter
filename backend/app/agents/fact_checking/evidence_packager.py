"""Evidence package assembly."""

from __future__ import annotations

from collections.abc import Sequence

from app.agents.fact_checking.confidence_engine import ConfidenceResult
from app.agents.fact_checking.cross_source_validator import ClaimResult
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle

logger = get_logger("factcheck.evidence")


def build_package(
    article: CollectedArticle,
    claim_results: Sequence[ClaimResult],
    citations: list[dict],
    supporting_sources: list[str],
    confidence: ConfidenceResult,
    notes: str,
) -> dict:
    package = {
        "article_id": str(article.id),
        "title": article.title,
        "claims": [
            {
                "claim_text": c.claim_text,
                "claim_type": c.claim_type.value,
                "status": c.status.value,
                "support_score": c.support_score,
                "corroborating_sources": c.corroborating_sources,
            }
            for c in claim_results
        ],
        "citations": citations,
        "supporting_sources": supporting_sources,
        "confidence_score": confidence.overall_confidence_score,
        "verification_status": confidence.verification_status.value,
        "verification_notes": notes,
    }
    logger.info("evidence_package_created", article_id=str(article.id))
    return package
