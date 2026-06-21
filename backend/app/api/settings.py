"""Runtime settings API (mounted at /api/settings).

Lets the operator UI read the editable configuration schema + current values
and update them. Protected by the reviewer dependency. Secrets are never
returned in plaintext.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_reviewer
from app.services import runtime_config

router = APIRouter(tags=["settings"], dependencies=[Depends(require_reviewer)])


@router.get("")
async def get_settings_config() -> dict[str, Any]:
    """Return the editable field schema, current values, and secret-set flags."""
    return runtime_config.get_config()


@router.put("")
async def update_settings_config(
    updates: dict[str, Any] = Body(..., description="Partial map of config key -> value"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Persist + apply a partial config update; returns the changed keys."""
    result = await runtime_config.update_config(session, updates)
    return {**result, **runtime_config.get_config()}
