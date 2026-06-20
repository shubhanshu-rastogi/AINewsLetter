"""Visual generation API endpoints (mounted at /api/visuals)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.visual_generation.asset_storage import get_storage
from app.agents.visual_generation.exceptions import VisualNotFoundError
from app.agents.visual_generation.visual_agent import VisualGenerationAgent
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.enums import VisualKind
from app.models.generated_visual import GeneratedVisual
from app.schemas.visual import (
    GenerateResponse,
    RegenerateResponse,
    VisualMetadataResponse,
    VisualPreview,
    VisualRead,
)

router = APIRouter(tags=["visuals"])


def _preview(visual: GeneratedVisual) -> VisualPreview:
    storage = get_storage()
    return VisualPreview(
        visual_id=str(visual.id),
        visual_kind=visual.visual_kind,
        file_path=visual.file_path,
        preview_url=storage.url_for(visual.file_path) if visual.file_path else None,
        width=visual.width,
        height=visual.height,
        version=visual.version,
        created_at=visual.created_at,
    )


# --- generation --- #
@router.post("/generate/{newsletter_id}", response_model=GenerateResponse)
async def generate_all(newsletter_id: uuid.UUID) -> GenerateResponse:
    agent = VisualGenerationAgent(AsyncSessionLocal)
    result = await agent.generate_all_visuals(str(newsletter_id))
    return GenerateResponse(**result)


@router.post("/generate/{newsletter_id}/cover")
async def generate_cover(newsletter_id: uuid.UUID) -> dict:
    agent = VisualGenerationAgent(AsyncSessionLocal)
    return await agent.generate_cover_only(str(newsletter_id))


@router.post("/generate/{newsletter_id}/carousel")
async def generate_carousel(newsletter_id: uuid.UUID) -> dict:
    agent = VisualGenerationAgent(AsyncSessionLocal)
    return await agent.generate_carousel_only(str(newsletter_id))


# --- reads --- #
@router.get("/{newsletter_id}", response_model=list[VisualPreview])
async def list_visuals(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[VisualPreview]:
    stmt = select(GeneratedVisual).where(GeneratedVisual.newsletter_id == newsletter_id)
    visuals = (await session.execute(stmt)).scalars().all()
    return [_preview(v) for v in visuals]


@router.get("/{newsletter_id}/cover", response_model=VisualRead)
async def get_cover(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> GeneratedVisual:
    visual = await session.scalar(
        select(GeneratedVisual).where(
            GeneratedVisual.newsletter_id == newsletter_id,
            GeneratedVisual.visual_kind == VisualKind.COVER.value,
        )
    )
    if visual is None:
        raise HTTPException(status_code=404, detail="Cover not found.")
    return visual


@router.get("/{newsletter_id}/carousel", response_model=list[VisualRead])
async def get_carousel(newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[GeneratedVisual]:
    stmt = (
        select(GeneratedVisual)
        .where(
            GeneratedVisual.newsletter_id == newsletter_id,
            GeneratedVisual.visual_kind == VisualKind.CAROUSEL_SLIDE.value,
        )
        .order_by(GeneratedVisual.slide_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{newsletter_id}/metadata", response_model=VisualMetadataResponse)
async def get_metadata(
    newsletter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> VisualMetadataResponse:
    agent = VisualGenerationAgent(AsyncSessionLocal)
    stmt = select(GeneratedVisual).where(GeneratedVisual.newsletter_id == newsletter_id)
    visuals = (await session.execute(stmt)).scalars().all()
    return VisualMetadataResponse(
        newsletter_id=str(newsletter_id),
        visuals=[agent.create_visual_metadata(v) for v in visuals],
    )


@router.post("/{visual_id}/regenerate", response_model=RegenerateResponse)
async def regenerate(visual_id: uuid.UUID) -> RegenerateResponse:
    agent = VisualGenerationAgent(AsyncSessionLocal)
    try:
        result = await agent.version_visual(str(visual_id))
    except VisualNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual not found.") from exc
    return RegenerateResponse(**result)
