"""Fact-checking API endpoints (mounted at /api/facts)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fact_checking.fact_check_agent import FactCheckAgent
from app.api.deps import get_session
from app.db.session import AsyncSessionLocal
from app.models.citation import Citation
from app.models.evidence_package import EvidencePackage
from app.models.fact_check_result import FactCheckResult
from app.schemas.fact_check import (
    CitationRead,
    EvidencePackageRead,
    FactCheckResultRead,
    FactCheckStats,
)
from app.services.fact_check_stats import get_fact_check_stats

router = APIRouter(tags=["fact-checking"])


@router.post("/verify")
async def verify_all() -> dict:
    agent = FactCheckAgent(AsyncSessionLocal)
    return await agent.run()


@router.post("/verify/{article_id}")
async def verify_one(article_id: uuid.UUID) -> dict:
    agent = FactCheckAgent(AsyncSessionLocal)
    return await agent.run([str(article_id)])


@router.get("/results", response_model=list[FactCheckResultRead])
async def list_results(session: AsyncSession = Depends(get_session)) -> list[FactCheckResult]:
    stmt = select(FactCheckResult).order_by(FactCheckResult.overall_confidence_score.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.get("/results/{article_id}", response_model=FactCheckResultRead)
async def get_result(article_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> FactCheckResult:
    result = await session.scalar(select(FactCheckResult).where(FactCheckResult.article_id == article_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Fact-check result not found.")
    return result


@router.get("/evidence/{article_id}", response_model=EvidencePackageRead)
async def get_evidence(article_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> EvidencePackage:
    package = await session.scalar(select(EvidencePackage).where(EvidencePackage.article_id == article_id))
    if package is None:
        raise HTTPException(status_code=404, detail="Evidence package not found.")
    return package


@router.get("/citations/{article_id}", response_model=list[CitationRead])
async def get_citations(article_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[Citation]:
    stmt = select(Citation).where(Citation.article_id == article_id)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/statistics", response_model=FactCheckStats)
async def statistics(session: AsyncSession = Depends(get_session)) -> FactCheckStats:
    return await get_fact_check_stats(session)
