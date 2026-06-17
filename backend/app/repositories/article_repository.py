"""Collected article repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_article import CollectedArticle
from app.models.enums import ArticleStatus
from app.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[CollectedArticle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CollectedArticle, session)

    async def get_by_url(self, url: str) -> CollectedArticle | None:
        result = await self.session.execute(
            select(CollectedArticle).where(CollectedArticle.url == url)
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, status: ArticleStatus) -> Sequence[CollectedArticle]:
        result = await self.session.execute(
            select(CollectedArticle).where(CollectedArticle.status == status)
        )
        return result.scalars().all()

    async def list_by_source(self, source_id: uuid.UUID) -> Sequence[CollectedArticle]:
        result = await self.session.execute(
            select(CollectedArticle).where(CollectedArticle.source_id == source_id)
        )
        return result.scalars().all()
