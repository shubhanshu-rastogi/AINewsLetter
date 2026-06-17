"""Shared API dependencies (dependency-injection wiring).

Endpoints depend on these callables rather than importing infrastructure
directly, which keeps the routing layer thin and testable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for the request lifetime."""
    async for session in get_db():
        yield session


def get_app_settings() -> Settings:
    """Return application settings."""
    return get_settings()
