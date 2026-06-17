"""Newsletter repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import NewsletterStatus
from app.models.newsletter import Newsletter
from app.repositories.base import BaseRepository


class NewsletterRepository(BaseRepository[Newsletter]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Newsletter, session)

    async def get_by_issue_number(self, issue_number: int) -> Newsletter | None:
        result = await self.session.execute(
            select(Newsletter).where(Newsletter.issue_number == issue_number)
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, status: NewsletterStatus) -> Sequence[Newsletter]:
        result = await self.session.execute(
            select(Newsletter).where(Newsletter.status == status)
        )
        return result.scalars().all()

    async def get_with_sections(self, id: uuid.UUID) -> Newsletter | None:
        result = await self.session.execute(
            select(Newsletter)
            .where(Newsletter.id == id)
            .options(selectinload(Newsletter.sections))
        )
        return result.scalar_one_or_none()
