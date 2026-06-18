"""Shared API dependencies (dependency-injection wiring).

Endpoints depend on these callables rather than importing infrastructure
directly, which keeps the routing layer thin and testable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings, settings
from app.db.session import get_db


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for the request lifetime."""
    async for session in get_db():
        yield session


def get_app_settings() -> Settings:
    """Return application settings."""
    return get_settings()


async def require_reviewer(authorization: str | None = Header(default=None)) -> dict:
    """Placeholder auth for protected review endpoints.

    If ``REVIEW_AUTH_TOKEN`` is configured, a matching ``Authorization: Bearer``
    header is required; otherwise access is allowed (development default).
    Replace with real OIDC/JWT auth when available.
    """
    token = settings.REVIEW_AUTH_TOKEN
    if token:
        if authorization != f"Bearer {token}":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: valid reviewer token required.",
            )
    return {"principal": "reviewer"}
