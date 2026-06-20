"""Publication record repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PublicationChannel
from app.models.publication_record import PublicationRecord
from app.repositories.base import BaseRepository


class PublicationRepository(BaseRepository[PublicationRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PublicationRecord, session)

    async def list_by_newsletter(self, newsletter_id: uuid.UUID) -> Sequence[PublicationRecord]:
        result = await self.session.execute(
            select(PublicationRecord).where(PublicationRecord.newsletter_id == newsletter_id)
        )
        return result.scalars().all()

    async def get_by_newsletter_and_channel(
        self, newsletter_id: uuid.UUID, channel: PublicationChannel
    ) -> PublicationRecord | None:
        result = await self.session.execute(
            select(PublicationRecord).where(
                PublicationRecord.newsletter_id == newsletter_id,
                PublicationRecord.channel == channel,
            )
        )
        return result.scalars().first()
