"""Review version history tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_version import ReviewVersion


async def next_version_number(session: AsyncSession, newsletter_id: uuid.UUID) -> int:
    current = await session.scalar(
        select(func.max(ReviewVersion.version_number)).where(
            ReviewVersion.newsletter_id == newsletter_id
        )
    )
    return (current or 0) + 1


async def record_version(
    session: AsyncSession,
    newsletter_id: uuid.UUID,
    *,
    review_session_id: uuid.UUID | None,
    feedback_summary: list | None = None,
    regeneration_plan: dict | None = None,
    changed_sections: list | None = None,
    reviewer_decision: str | None = None,
) -> ReviewVersion:
    version = ReviewVersion(
        newsletter_id=newsletter_id,
        review_session_id=review_session_id,
        version_number=await next_version_number(session, newsletter_id),
        feedback_summary=feedback_summary,
        regeneration_plan=regeneration_plan,
        changed_sections=changed_sections,
        reviewer_decision=reviewer_decision,
    )
    session.add(version)
    return version
