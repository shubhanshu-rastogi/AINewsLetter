"""Content source repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_source import ContentSource
from app.repositories.base import BaseRepository


class SourceRepository(BaseRepository[ContentSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ContentSource, session)

    async def get_by_url(self, source_url: str) -> ContentSource | None:
        result = await self.session.execute(
            select(ContentSource).where(ContentSource.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[ContentSource]:
        result = await self.session.execute(
            select(ContentSource).where(ContentSource.is_active.is_(True))
        )
        return result.scalars().all()
