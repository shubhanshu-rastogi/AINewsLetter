"""Newsletter writer API endpoints (mounted at /api/newsletters)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.newsletter_writer.exceptions import UnknownSectionError
from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.carousel_outline import CarouselOutline
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.newsletter_version import NewsletterVersion
from app.schemas.newsletter import NewsletterRead
from app.schemas.writer import (
    CarouselRead,
    GenerateRequest,
    LinkedInPostRead,
    NewsletterDraftRead,
    NewsletterGenerateResponse,
    NewsletterStats,
    NewsletterVersionRead,
    RegenerateRequest,
)
from app.services.newsletter_stats import get_newsletter_stats

router = APIRouter(tags=["newsletters"])


@router.post("/generate", response_model=NewsletterGenerateResponse)
async def generate(payload: GenerateRequest | None = None) -> NewsletterGenerateResponse:
    payload = payload or GenerateRequest()
    agent = NewsletterWriterAgent(AsyncSessionLocal)
    result = await agent.generate_newsletter(
        article_ids=payload.article_ids,
        newsletter_id=payload.newsletter_id,
        created_by=payload.created_by,
    )
    return NewsletterGenerateResponse(
        newsletter_id=result["newsletter_id"],
        version=result["version"],
        word_count=result["word_count"],
        reading_time_minutes=result["reading_time_minutes"],
        sections_generated=result["sections_generated"],
        content=result["content"],
    )


@router.get("/statistics", response_model=NewsletterStats)
async def statistics(session: AsyncSession = Depends(get_session)) -> NewsletterStats:
    return await get_newsletter_stats(session)


@router.get("", response_model=list[NewsletterRead])
async def list_newsletters(session: AsyncSession = Depends(get_session)) -> list[Newsletter]:
    stmt = select(Newsletter).order_by(Newsletter.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("/{newsletter_id}/regenerate")
async def regenerate(newsletter_id: uuid.UUID, payload: RegenerateRequest) -> dict:
    agent = NewsletterWriterAgent(AsyncSessionLocal)
    try:
        return await agent.regenerate_section(
            str(newsletter_id),
            payload.section,
            reason=payload.reason,
            changed_by=payload.changed_by,
        )
    except UnknownSectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AttributeError as exc:  # no draft yet
        raise HTTPException(status_code=404, detail="Newsletter draft not found.") from exc


@router.get("/{newsletter_id}", response_model=NewsletterDraftRead)
async def get_newsletter(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> NewsletterDraft:
    draft = await session.scalar(select(NewsletterDraft).where(NewsletterDraft.newsletter_id == newsletter_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="Newsletter draft not found.")
    return draft


@router.get("/{newsletter_id}/versions", response_model=list[NewsletterVersionRead])
async def get_versions(
    newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[NewsletterVersion]:
    stmt = (
        select(NewsletterVersion)
        .where(NewsletterVersion.newsletter_id == newsletter_id)
        .order_by(NewsletterVersion.version_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{newsletter_id}/linkedin", response_model=list[LinkedInPostRead])
async def get_linkedin(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[LinkedInPost]:
    stmt = select(LinkedInPost).where(LinkedInPost.newsletter_id == newsletter_id)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{newsletter_id}/carousel", response_model=CarouselRead)
async def get_carousel(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> CarouselOutline:
    carousel = await session.scalar(select(CarouselOutline).where(CarouselOutline.newsletter_id == newsletter_id))
    if carousel is None:
        raise HTTPException(status_code=404, detail="Carousel not found.")
    return carousel


@router.get("/{newsletter_id}/subjects")
async def get_subjects(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    draft = await session.scalar(select(NewsletterDraft).where(NewsletterDraft.newsletter_id == newsletter_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="Newsletter draft not found.")
    return {"email_subjects": draft.email_subjects or []}
