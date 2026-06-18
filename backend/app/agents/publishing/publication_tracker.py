"""Publication record bookkeeping (one record per newsletter+channel)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PublicationChannel, PublicationStatus
from app.models.publication_record import PublicationRecord


async def get_or_create_record(
    session: AsyncSession, newsletter_id: uuid.UUID, channel: PublicationChannel
) -> PublicationRecord:
    record = await session.scalar(
        select(PublicationRecord).where(
            PublicationRecord.newsletter_id == newsletter_id,
            PublicationRecord.channel == channel,
        )
    )
    if record is None:
        record = PublicationRecord(
            newsletter_id=newsletter_id, channel=channel,
            publication_status=PublicationStatus.PENDING,
        )
        session.add(record)
        await session.flush()
    return record


async def list_publications(session: AsyncSession, limit: int = 100) -> Sequence[PublicationRecord]:
    stmt = select(PublicationRecord).order_by(PublicationRecord.created_at.desc()).limit(limit)
    return (await session.execute(stmt)).scalars().all()


async def for_newsletter(
    session: AsyncSession, newsletter_id: uuid.UUID
) -> Sequence[PublicationRecord]:
    stmt = select(PublicationRecord).where(PublicationRecord.newsletter_id == newsletter_id)
    return (await session.execute(stmt)).scalars().all()
