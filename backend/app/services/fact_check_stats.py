"""Fact-checking statistics."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citation import Citation
from app.models.collected_article import CollectedArticle
from app.models.enums import VerificationStatus
from app.models.verified_claim import VerifiedClaim
from app.schemas.fact_check import FactCheckStats


async def _count_status(session: AsyncSession, status: VerificationStatus) -> int:
    value = await session.scalar(
        select(func.count()).select_from(CollectedArticle).where(CollectedArticle.verification_status == status.value)
    )
    return int(value or 0)


async def get_fact_check_stats(session: AsyncSession) -> FactCheckStats:
    verified = await _count_status(session, VerificationStatus.VERIFIED)
    rejected = await _count_status(session, VerificationStatus.REJECTED)
    review = await _count_status(session, VerificationStatus.REVIEW_REQUIRED)

    avg = await session.scalar(select(func.avg(CollectedArticle.overall_confidence_score)))
    citations = await session.scalar(select(func.count()).select_from(Citation))
    claims = await session.scalar(select(func.count()).select_from(VerifiedClaim))

    top_rows = await session.execute(
        select(CollectedArticle.source_category, func.count())
        .where(CollectedArticle.verification_status.is_not(None))
        .group_by(CollectedArticle.source_category)
        .order_by(func.count().desc())
        .limit(10)
    )

    return FactCheckStats(
        articles_verified=verified,
        articles_rejected=rejected,
        articles_requiring_review=review,
        average_confidence_score=round(float(avg), 2) if avg else 0.0,
        citations_created=int(citations or 0),
        claims_extracted=int(claims or 0),
        top_verified_sources={(k or "uncategorized"): c for k, c in top_rows},
    )
