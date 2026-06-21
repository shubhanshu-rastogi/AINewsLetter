"""Authentication API (mounted at /api/auth).

Single shared admin token. The frontend calls ``/config`` (public) to learn
whether auth is required, ``/login`` to validate the token, and sends the token
as ``Authorization: Bearer <token>`` on protected routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import require_reviewer
from app.core.config import settings

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    token: str = ""


@router.get("/config")
async def auth_config() -> dict:
    """Public: whether a token is required to use the app."""
    return {"auth_required": bool(settings.REVIEW_AUTH_TOKEN)}


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    """Validate the admin token (no-op when auth is disabled)."""
    token = settings.REVIEW_AUTH_TOKEN
    if token and payload.token != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {"ok": True, "auth_required": bool(token)}


@router.get("/verify", dependencies=[Depends(require_reviewer)])
async def verify() -> dict:
    """Confirm the bearer token is valid (used to re-validate a stored session)."""
    return {"ok": True}
