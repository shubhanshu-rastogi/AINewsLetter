"""FactCheckAgent - verifies, cites, scores, and packages evidence."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fact_checking import (
    citation_builder,
    confidence_engine,
    cross_source_validator,
    evidence_packager,
    source_verifier,
)
from app.agents.fact_checking.confidence_engine import ConfidenceResult
from app.agents.fact_checking.cross_source_validator import Claim, ClaimResult
from app.agents.relevance_filter.scoring_engine import freshness_dimension
from app.core.config import settings
from app.core.logging import get_logger
from app.models.citation import Citation
from app.models.collected_article import CollectedArticle
from app.models.enums import VerificationStatus
from app.models.evidence_package import EvidencePackage
from app.models.fact_check_result import FactCheckResult
from app.models.verified_claim import VerifiedClaim

logger = get_logger("factcheck")


async def llm_extract_claims(article: CollectedArticle) -> list[str] | None:
    """Optional LLM claim extraction hook (mocked in tests; off by default)."""
    return None  # network/LLM wiring lives behind ENABLE_LLM_FACTCHECK; mock in tests


def _keywords(text: str) -> set[str]:
    return cross_source_validator._keywords(text)  # noqa: SLF001 - shared helper


class FactCheckAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    # ----- unit operations ----- #
    async def extract_claims(self, article: CollectedArticle) -> list[Claim]:
        text = f"{article.title or ''}. {article.summary or ''} {article.raw_content or ''}"
        claims = cross_source_validator.extract_claims(text)
        if settings.ENABLE_LLM_FACTCHECK:
            extra = await llm_extract_claims(article)
            if extra:
                from app.models.enums import ClaimType

                existing = {c.text for c in claims}
                claims.extend(Claim(text=t, claim_type=ClaimType.FACT) for t in extra if t not in existing)
        return claims

    def validate_claims(self, claims, article, tier, corpus) -> list[ClaimResult]:
        return cross_source_validator.validate_claims(claims, article, tier, corpus)

    def _supporting_sources(
        self, article: CollectedArticle, corpus: Sequence[CollectedArticle]
    ) -> list[CollectedArticle]:
        anchor = _keywords(f"{article.title or ''} {article.summary or ''}")
        supporting = []
        for other in corpus:
            if other.id == article.id or other.source_id == article.source_id:
                continue
            other_kw = _keywords(f"{other.title or ''} {other.summary or ''}")
            if len(anchor & other_kw) >= 2:
                supporting.append(other)
        return supporting

    def generate_citations(self, article, supporting) -> list[dict]:
        return citation_builder.build_citations(article, supporting)

    def calculate_confidence(
        self, *, source_credibility, claim_results, url_accessible, freshness, citations_count
    ) -> ConfidenceResult:
        return confidence_engine.compute_confidence(
            source_credibility=source_credibility,
            claim_results=claim_results,
            url_accessible=url_accessible,
            freshness=freshness,
            citations_count=citations_count,
        )

    def create_evidence_package(self, article, claim_results, citations, supporting_sources, confidence, notes) -> dict:
        return evidence_packager.build_package(article, claim_results, citations, supporting_sources, confidence, notes)

    async def _clear_existing(self, session: AsyncSession, article_id: uuid.UUID) -> None:
        for model in (Citation, VerifiedClaim, FactCheckResult, EvidencePackage):
            await session.execute(delete(model).where(model.article_id == article_id))

    async def update_database(
        self,
        session: AsyncSession,
        article: CollectedArticle,
        *,
        url_check,
        confidence: ConfidenceResult,
        claim_results: list[ClaimResult],
        citations: list[dict],
        package: dict,
        supporting_sources: list[str],
        notes: str,
    ) -> None:
        await self._clear_existing(session, article.id)
        now = datetime.now(timezone.utc)

        session.add(
            FactCheckResult(
                article_id=article.id,
                url_accessible=url_check.accessible,
                source_credibility_score=confidence.source_credibility_score,
                claim_verification_score=confidence.claim_verification_score,
                cross_source_score=confidence.cross_source_score,
                freshness_score=confidence.freshness_score,
                evidence_score=confidence.evidence_score,
                overall_confidence_score=confidence.overall_confidence_score,
                verification_status=confidence.verification_status.value,
                fact_check_notes=notes,
                verified_at=now,
            )
        )
        for cite in citations:
            session.add(
                Citation(
                    article_id=article.id,
                    title=cite["title"],
                    source_name=cite["source_name"],
                    source_url=cite["source_url"],
                    publication_date=article.published_date if cite["source_url"] == article.url else None,
                    retrieval_timestamp=now,
                )
            )
        for cr in claim_results:
            session.add(
                VerifiedClaim(
                    article_id=article.id,
                    claim_text=cr.claim_text,
                    claim_type=cr.claim_type.value,
                    verification_status=cr.status.value,
                    support_score=cr.support_score,
                    corroborating_sources=cr.corroborating_sources,
                )
            )
        session.add(
            EvidencePackage(
                article_id=article.id,
                confidence_score=confidence.overall_confidence_score,
                verification_status=confidence.verification_status.value,
                supporting_sources=supporting_sources,
                verification_notes=notes,
                package=package,
            )
        )

        article.verification_status = confidence.verification_status.value
        article.overall_confidence_score = confidence.overall_confidence_score
        article.verified_at = now

    async def verify_article(
        self,
        session: AsyncSession,
        article: CollectedArticle,
        corpus: Sequence[CollectedArticle],
    ) -> dict[str, Any]:
        logger.info("fact_check_started", article_id=str(article.id))

        url_check = await source_verifier.verify_url(article.url)
        tier, credibility = source_verifier.verify_source(article)
        date_valid = source_verifier.verify_date(article.published_date)

        claims = await self.extract_claims(article)
        claim_results = self.validate_claims(claims, article, tier, corpus)
        supporting = self._supporting_sources(article, corpus)
        citations = self.generate_citations(article, supporting)
        freshness = freshness_dimension(article.published_date)

        confidence = self.calculate_confidence(
            source_credibility=credibility,
            claim_results=claim_results,
            url_accessible=url_check.accessible,
            freshness=freshness,
            citations_count=len(citations),
        )

        supporting_names = [s.source.source_name if s.source else s.url for s in supporting]
        notes = (
            f"trust={tier.value}; url_accessible={url_check.accessible}; "
            f"date_valid={date_valid}; claims={len(claim_results)}; "
            f"supporting_sources={len(supporting)}"
        )
        package = self.create_evidence_package(article, claim_results, citations, supporting_names, confidence, notes)
        await self.update_database(
            session,
            article,
            url_check=url_check,
            confidence=confidence,
            claim_results=claim_results,
            citations=citations,
            package=package,
            supporting_sources=supporting_names,
            notes=notes,
        )

        logger.info(
            "fact_check_completed",
            article_id=str(article.id),
            status=confidence.verification_status.value,
            confidence=confidence.overall_confidence_score,
        )
        return {
            "article_id": str(article.id),
            "verification_status": confidence.verification_status.value,
            "overall_confidence_score": confidence.overall_confidence_score,
            "claims_extracted": len(claim_results),
            "citations_created": len(citations),
        }

    def update_workflow_state(
        self, results: list[dict], rejected_ids: list[str], kept_ids: list[str]
    ) -> dict[str, Any]:
        return {"fact_check_results": results, "selected_article_ids": kept_ids}

    # ----- orchestration ----- #
    async def run(self, article_ids: Sequence[str] | None = None) -> dict[str, Any]:
        async with self.session_factory() as session:
            stmt = select(CollectedArticle)
            if article_ids is not None:
                ids = [uuid.UUID(str(a)) for a in article_ids]
                if not ids:
                    return {"fact_check_results": [], "rejected": [], "selected_article_ids": []}
                target = list((await session.execute(stmt.where(CollectedArticle.id.in_(ids)))).scalars().all())
            else:
                target = list(
                    (await session.execute(stmt.where(CollectedArticle.is_selected.is_(True)))).scalars().all()
                )

            corpus = list((await session.execute(select(CollectedArticle))).scalars().all())

            results: list[dict] = []
            rejected: list[str] = []
            kept: list[str] = []
            for article in target:
                summary = await self.verify_article(session, article, corpus)
                results.append(summary)
                if summary["verification_status"] == VerificationStatus.REJECTED.value:
                    rejected.append(summary["article_id"])
                else:
                    kept.append(summary["article_id"])

            await session.commit()

        logger.info("fact_check_run_completed", verified=len(kept), rejected=len(rejected))
        return {
            "fact_check_results": results,
            "rejected": rejected,
            "selected_article_ids": kept,
        }
