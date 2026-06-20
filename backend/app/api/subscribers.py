"""Subscriber API endpoints (mounted at /api/subscribers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.publishing.subscriber_manager import SubscriberManager
from app.api.deps import require_reviewer
from app.db.session import AsyncSessionLocal
from app.models.enums import SubscriberStatus
from app.models.subscriber import Subscriber
from app.schemas.publishing import (
    SubscribeRequest,
    SubscriberRead,
    SubscriberStats,
    UnsubscribeRequest,
)

router = APIRouter(tags=["subscribers"], dependencies=[Depends(require_reviewer)])


def _manager() -> SubscriberManager:
    return SubscriberManager(AsyncSessionLocal)


@router.post("", response_model=SubscriberRead, status_code=201)
async def subscribe(payload: SubscribeRequest) -> Subscriber:
    return await _manager().subscribe(str(payload.email), payload.name, payload.source)


@router.post("/unsubscribe", response_model=SubscriberRead)
async def unsubscribe(payload: UnsubscribeRequest) -> Subscriber:
    sub = await _manager().unsubscribe(str(payload.email))
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscriber not found.")
    return sub


@router.get("", response_model=list[SubscriberRead])
async def list_subscribers(
    status: SubscriberStatus | None = Query(default=None),
) -> list[Subscriber]:
    return list(await _manager().list_subscribers(status=status))


@router.get("/stats", response_model=SubscriberStats)
async def subscriber_stats() -> SubscriberStats:
    return SubscriberStats(**await _manager().statistics())
