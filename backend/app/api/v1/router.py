"""Versioned API (v1) router aggregation.

Domain routers (runs, reviews, feedback, sources, ...) will be added here as
they are implemented. For now it exposes only a meta endpoint so the prefix is
mounted and discoverable.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import APIResponse

api_router = APIRouter()


@api_router.get("/", response_model=APIResponse[dict])
async def api_root() -> APIResponse[dict]:
    """API v1 entry point. Lists available resource groups (placeholder)."""
    return APIResponse(
        data={"resources": []},
        message="Agentic AI Newsletter Platform API v1",
    )


# Future routers (placeholders - not yet implemented):
# from app.api.v1.endpoints import runs, reviews, feedback, sources, publications
# api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
# api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
# api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
