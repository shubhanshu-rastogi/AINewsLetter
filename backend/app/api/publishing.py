"""Publishing + publications API endpoints (mounted at /api)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.publishing.exceptions import (
    PublicationNotApprovedError,
    PublishError,
    ValidationFailedError,
)
from app.agents.publishing.publisher_agent import PublisherAgent
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.publication_analytics import PublicationAnalytics
from app.models.publication_record import PublicationRecord
from app.schemas.publishing import (
    AnalyticsRead,
    EmailPackageResponse,
    PublicationRecordRead,
    PublishRequest,
    PublishResponse,
)

# Publishing actions (POST /api/publish/...)
publish_router = APIRouter(tags=["publishing"])
# Read-only publication history/analytics (GET /api/publications/...)
publications_router = APIRouter(tags=["publications"])


def _agent() -> PublisherAgent:
    return PublisherAgent(AsyncSessionLocal)


@publish_router.post("/{newsletter_id}", response_model=PublishResponse)
async def publish(newsletter_id: uuid.UUID, payload: PublishRequest | None = None) -> PublishResponse:
    payload = payload or PublishRequest()
    try:
        result = await _agent().publish_newsletter(str(newsletter_id), payload.channels)
    except PublicationNotApprovedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PublishResponse(**result)


@publish_router.post("/{newsletter_id}/beehiiv", response_model=PublishResponse)
async def publish_beehiiv(newsletter_id: uuid.UUID) -> PublishResponse:
    try:
        result = await _agent().publish_newsletter(str(newsletter_id), ["beehiiv"])
    except PublicationNotApprovedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PublishResponse(**result)


@publish_router.post("/{newsletter_id}/linkedin", response_model=PublishResponse)
async def publish_linkedin(newsletter_id: uuid.UUID) -> PublishResponse:
    try:
        result = await _agent().publish_newsletter(str(newsletter_id), ["linkedin"])
    except PublicationNotApprovedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PublishResponse(**result)


@publish_router.post("/{newsletter_id}/email", response_model=EmailPackageResponse)
async def prepare_email(newsletter_id: uuid.UUID) -> EmailPackageResponse:
    try:
        package = await _agent().prepare_email(str(newsletter_id))
    except PublicationNotApprovedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EmailPackageResponse(**package)


@publications_router.get("", response_model=list[PublicationRecordRead])
async def list_publications(session: AsyncSession = Depends(get_session)) -> list[PublicationRecord]:
    stmt = select(PublicationRecord).order_by(PublicationRecord.created_at.desc()).limit(200)
    return list((await session.execute(stmt)).scalars().all())


@publications_router.get("/{newsletter_id}", response_model=list[PublicationRecordRead])
async def get_publications(
    newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[PublicationRecord]:
    stmt = select(PublicationRecord).where(PublicationRecord.newsletter_id == newsletter_id)
    return list((await session.execute(stmt)).scalars().all())


@publications_router.get("/{newsletter_id}/analytics", response_model=list[AnalyticsRead])
async def get_analytics(
    newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[PublicationAnalytics]:
    stmt = select(PublicationAnalytics).where(PublicationAnalytics.newsletter_id == newsletter_id)
    return list((await session.execute(stmt)).scalars().all())


@publications_router.post("/{publication_id}/retry", response_model=PublishResponse)
async def retry_publication(publication_id: uuid.UUID) -> PublishResponse:
    try:
        out = await _agent().retry_publication(str(publication_id))
    except ValidationFailedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # retry_publication re-runs a single channel; surface the full publish result.
    result = out["result"] or {}
    return PublishResponse(
        newsletter_id="", overall=result.get("status", "unknown"),
        publish_status=result.get("status", "unknown"),
        channels={out["channel"]: result},
    )
