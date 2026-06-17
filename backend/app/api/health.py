"""Root-level health and readiness probes (Kubernetes/Docker friendly).

These live outside the versioned API prefix so orchestrators can probe stable
paths (``/health`` and ``/ready``).
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.schemas.health import HealthStatus, ReadinessStatus
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """Liveness probe - the process is running."""
    return health_service.get_health()


@router.get("/ready", response_model=ReadinessStatus)
async def ready(response: Response) -> ReadinessStatus:
    """Readiness probe - required dependencies are reachable."""
    result = await health_service.get_readiness()
    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
