"""Generic async repository with pagination.

Concrete repositories subclass :class:`BaseRepository` and add domain queries.
No business rules live here.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)


@dataclass(slots=True)
class Page(Generic[ModelType]):
    """A page of results plus pagination metadata."""

    items: Sequence[ModelType]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class BaseRepository(Generic[ModelType]):
    """Async CRUD repository for a single model type."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelType]:
        result = await self.session.execute(select(self.model).limit(limit).offset(offset))
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def paginate(self, *, page: int = 1, page_size: int = 50) -> Page[ModelType]:
        page = max(page, 1)
        page_size = max(min(page_size, 200), 1)
        total = await self.count()
        result = await self.session.execute(select(self.model).limit(page_size).offset((page - 1) * page_size))
        return Page(
            items=result.scalars().all(),
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create(self, data: dict[str, Any]) -> ModelType:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType, data: dict[str, Any]) -> ModelType:
        for key, value in data.items():
            setattr(obj, key, value)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.flush()
