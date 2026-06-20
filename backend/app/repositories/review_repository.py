"""Review session repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_session import ReviewSession
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[ReviewSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ReviewSession, session)

    async def list_by_newsletter(self, newsletter_id: uuid.UUID) -> Sequence[ReviewSession]:
        result = await self.session.execute(select(ReviewSession).where(ReviewSession.newsletter_id == newsletter_id))
        return result.scalars().all()
