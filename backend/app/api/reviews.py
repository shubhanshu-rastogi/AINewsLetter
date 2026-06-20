"""Human review + feedback API endpoints (mounted at /api/reviews).

All endpoints are protected by the ``require_reviewer`` dependency.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.review_feedback.exceptions import ReviewSessionNotFoundError
from app.agents.review_feedback.feedback_agent import FeedbackAgent
from app.agents.review_feedback.review_agent import ReviewAgent
from app.api.deps import get_session, require_reviewer
from app.db.session import AsyncSessionLocal
from app.models.review_package import ReviewPackage
from app.models.review_session import ReviewSession
from app.models.review_version import ReviewVersion
from app.schemas.review import (
    ApprovalRequest,
    FeedbackRequest,
    FeedbackResponse,
    RegenerateRequest,
    RejectionRequest,
    ReviewPackageResponse,
    ReviewSessionRead,
    ReviewVersionRead,
)

router = APIRouter(tags=["reviews"], dependencies=[Depends(require_reviewer)])


@router.get("/{review_session_id}", response_model=ReviewSessionRead)
async def get_review(review_session_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ReviewSession:
    rs = await session.get(ReviewSession, review_session_id)
    if rs is None:
        raise HTTPException(status_code=404, detail="Review session not found.")
    return rs


@router.get("/newsletter/{newsletter_id}", response_model=list[ReviewSessionRead])
async def get_reviews_for_newsletter(
    newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ReviewSession]:
    stmt = (
        select(ReviewSession)
        .where(ReviewSession.newsletter_id == newsletter_id)
        .order_by(ReviewSession.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{review_session_id}/package", response_model=ReviewPackageResponse)
async def get_package(
    review_session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ReviewPackageResponse:
    pkg = await session.scalar(select(ReviewPackage).where(ReviewPackage.review_session_id == review_session_id))
    if pkg is None:
        raise HTTPException(status_code=404, detail="Review package not found.")
    return ReviewPackageResponse(review_session_id=str(review_session_id), package=pkg.package or {})


@router.get("/{review_session_id}/versions", response_model=list[ReviewVersionRead])
async def get_versions(
    review_session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ReviewVersion]:
    rs = await session.get(ReviewSession, review_session_id)
    if rs is None:
        raise HTTPException(status_code=404, detail="Review session not found.")
    stmt = (
        select(ReviewVersion)
        .where(ReviewVersion.newsletter_id == rs.newsletter_id)
        .order_by(ReviewVersion.version_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/{review_session_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(review_session_id: uuid.UUID, payload: FeedbackRequest) -> FeedbackResponse:
    agent = FeedbackAgent(AsyncSessionLocal)
    try:
        result = await agent.process_feedback(
            str(review_session_id),
            items=[item.model_dump() for item in payload.feedback_items],
            create_new_session=True,
        )
    except ReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review session not found.") from exc
    return FeedbackResponse(**result)


@router.post("/{review_session_id}/approve", response_model=ReviewSessionRead)
async def approve_review(
    review_session_id: uuid.UUID,
    payload: ApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewSession:
    agent = ReviewAgent(AsyncSessionLocal)
    try:
        await agent.approve(str(review_session_id), payload.comments, payload.reviewer)
    except ReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review session not found.") from exc
    return await session.get(ReviewSession, review_session_id)


@router.post("/{review_session_id}/reject", response_model=ReviewSessionRead)
async def reject_review(
    review_session_id: uuid.UUID,
    payload: RejectionRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewSession:
    agent = ReviewAgent(AsyncSessionLocal)
    try:
        await agent.reject(str(review_session_id), payload.comments, payload.reviewer)
    except ReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review session not found.") from exc
    return await session.get(ReviewSession, review_session_id)


@router.post("/{review_session_id}/regenerate")
async def regenerate(review_session_id: uuid.UUID, payload: RegenerateRequest) -> dict:
    """Trigger a single targeted regeneration action for the session's newsletter."""
    agent = FeedbackAgent(AsyncSessionLocal)
    async with AsyncSessionLocal() as session:
        review = await session.get(ReviewSession, review_session_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review session not found.")
        newsletter_id = str(review.newsletter_id)

    action = {
        "type": payload.action_type,
        "section": payload.section,
        "slide_number": payload.slide_number,
        "reason": payload.reason,
    }
    changed = await agent.execute_plan(newsletter_id, {"actions": [action]})
    return {"newsletter_id": newsletter_id, "changed_sections": changed}
