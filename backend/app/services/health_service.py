"""Health/readiness service.

Keeps dependency-probing logic out of the API layer.
"""

from __future__ import annotations

from app import __version__
from app.core.config import settings
from app.db.session import ping_database
from app.schemas.health import (
    DependencyStatus,
    HealthStatus,
    ReadinessStatus,
)


def get_health() -> HealthStatus:
    """Liveness: the process is up and able to serve requests."""
    return HealthStatus(
        status="ok",
        app=settings.APP_NAME,
        version=__version__,
        environment=settings.APP_ENV,
    )


async def get_readiness() -> ReadinessStatus:
    """Readiness: required dependencies (currently the database) are reachable."""
    db_healthy = await ping_database()
    dependencies = [DependencyStatus(name="database", healthy=db_healthy)]
    return ReadinessStatus(
        ready=all(dep.healthy for dep in dependencies),
        dependencies=dependencies,
    )
