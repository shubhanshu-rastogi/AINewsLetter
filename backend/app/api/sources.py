"""Content source + collection API endpoints (mounted at /api/sources)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.source_collection.collector import SourceCollectionAgent
from app.agents.source_collection.source_seed import seed_sources
from app.agents.source_collection.source_strategy import order_sources, strategy_view
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.content_source import ContentSource
from app.repositories.source_repository import SourceRepository
from app.schemas.source import (
    SourceCreate,
    SourceRead,
    SourceStrategyView,
    SourceUpdate,
)

router = APIRouter(tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[ContentSource]:
    repo = SourceRepository(session)
    if active_only:
        return list(await repo.list_active())
    return list(await repo.list(limit=200))


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    session: AsyncSession = Depends(get_session),
) -> ContentSource:
    repo = SourceRepository(session)
    return await repo.create(payload.model_dump())


@router.post("/seed")
async def seed_source_list(session: AsyncSession = Depends(get_session)) -> dict:
    created = await seed_sources(session)
    return {"created": created, "message": f"Seeded {created} new source(s)."}


@router.post("/collect")
async def collect_all(session: AsyncSession = Depends(get_session)) -> dict:
    agent = SourceCollectionAgent(AsyncSessionLocal)
    new_ids = await agent.collect_all_sources()
    return {"new_articles": len(new_ids), "article_ids": new_ids}


@router.get("/strategy", response_model=list[SourceStrategyView])
async def get_strategy(session: AsyncSession = Depends(get_session)) -> list[dict]:
    sources = (
        await session.execute(select(ContentSource).where(ContentSource.is_active.is_(True)))
    ).scalars().all()
    return [strategy_view(s) for s in order_sources(sources)]


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ContentSource:
    source = await SourceRepository(session).get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return source


@router.put("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> ContentSource:
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return await repo.update(source, payload.model_dump(exclude_unset=True))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    await repo.delete(source)


@router.post("/{source_id}/collect")
async def collect_one(source_id: uuid.UUID) -> dict:
    agent = SourceCollectionAgent(AsyncSessionLocal)
    result = await agent.collect_source(source_id)
    return {
        "source_id": result.source_id,
        "source_name": result.source_name,
        "collected": result.collected,
        "new": result.new,
        "duplicates": result.duplicates,
        "failed": result.failed,
        "error": result.error,
        "article_ids": result.article_ids,
    }
