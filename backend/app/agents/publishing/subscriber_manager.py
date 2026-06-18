"""Subscriber management."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.enums import SubscriberStatus
from app.models.subscriber import Subscriber

logger = get_logger("publishing.subscribers")


class SubscriberManager:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    async def subscribe(self, email: str, name: str | None = None, source: str = "api") -> Subscriber:
        async with self.session_factory() as session:
            existing = await session.scalar(select(Subscriber).where(Subscriber.email == email))
            if existing is not None:
                existing.status = SubscriberStatus.ACTIVE
                existing.unsubscribed_at = None
                if name:
                    existing.name = name
                await session.commit()
                await session.refresh(existing)
                return existing
            sub = Subscriber(email=email, name=name, source=source, status=SubscriberStatus.ACTIVE)
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            logger.info("subscriber_added", email=email, source=source)
            return sub

    async def unsubscribe(self, email: str) -> Subscriber | None:
        async with self.session_factory() as session:
            sub = await session.scalar(select(Subscriber).where(Subscriber.email == email))
            if sub is None:
                return None
            sub.status = SubscriberStatus.UNSUBSCRIBED
            sub.unsubscribed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(sub)
            logger.info("subscriber_unsubscribed", email=email)
            return sub

    async def list_subscribers(
        self, status: SubscriberStatus | None = None, limit: int = 200
    ) -> Sequence[Subscriber]:
        async with self.session_factory() as session:
            stmt = select(Subscriber).order_by(Subscriber.created_at.desc()).limit(limit)
            if status is not None:
                stmt = stmt.where(Subscriber.status == status)
            return (await session.execute(stmt)).scalars().all()

    async def statistics(self) -> dict:
        async with self.session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(Subscriber))
            rows = await session.execute(
                select(Subscriber.status, func.count()).group_by(Subscriber.status)
            )
            by_status = {str(k): c for k, c in rows}
            active = by_status.get(SubscriberStatus.ACTIVE.value, 0)
        return {
            "total": int(total or 0),
            "active": int(active),
            "unsubscribed": int(by_status.get(SubscriberStatus.UNSUBSCRIBED.value, 0)),
            "bounced": int(by_status.get(SubscriberStatus.BOUNCED.value, 0)),
            "by_status": by_status,
        }

    async def active_count(self) -> int:
        async with self.session_factory() as session:
            return int(await session.scalar(
                select(func.count()).select_from(Subscriber).where(
                    Subscriber.status == SubscriberStatus.ACTIVE
                )
            ) or 0)
