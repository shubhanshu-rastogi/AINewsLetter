"""Health/liveness/readiness probes + Prometheus metrics endpoint.

These live outside the versioned API prefix so orchestrators can probe stable
paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.metrics import render_metrics
from app.schemas.health import HealthStatus, ReadinessStatus
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """Aggregate health (liveness-style summary)."""
    return health_service.get_health()


@router.get("/health/live", response_model=HealthStatus)
async def live() -> HealthStatus:
    """Liveness probe - the process is running."""
    return health_service.get_health()


@router.get("/health/ready", response_model=ReadinessStatus)
async def ready(response: Response) -> ReadinessStatus:
    """Readiness probe - required dependencies are reachable."""
    result = await health_service.get_readiness()
    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


# Backwards-compatible alias for the original readiness path.
@router.get("/ready", response_model=ReadinessStatus, include_in_schema=False)
async def ready_alias(response: Response) -> ReadinessStatus:
    return await ready(response)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    if not settings.ENABLE_METRICS:
        return Response(status_code=404)
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
