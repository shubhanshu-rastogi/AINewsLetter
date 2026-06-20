"""Health/readiness service.

Keeps dependency-probing logic out of the API layer. Liveness is a cheap
process check; readiness probes the database, Redis, scheduler, and disk.
"""

from __future__ import annotations

import shutil

from app import __version__
from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis, is_real_redis
from app.db.session import ping_database
from app.schemas.health import (
    DependencyStatus,
    HealthStatus,
    ReadinessStatus,
)

logger = get_logger("health")

_MIN_FREE_DISK_BYTES = 200 * 1024 * 1024  # 200 MB


def get_health() -> HealthStatus:
    """Liveness: the process is up and able to serve requests."""
    return HealthStatus(
        status="ok",
        app=settings.APP_NAME,
        version=__version__,
        environment=settings.environment,
    )


async def _check_redis() -> DependencyStatus:
    # Redis is optional in development; the in-memory fallback is always healthy.
    if not settings.ENABLE_REDIS:
        return DependencyStatus(name="redis", healthy=True)
    try:
        redis = await get_redis()
        ok = await redis.ping()
        return DependencyStatus(name="redis", healthy=bool(ok) and is_real_redis())
    except Exception:  # noqa: BLE001
        return DependencyStatus(name="redis", healthy=False)


def _check_scheduler() -> DependencyStatus:
    if not settings.ENABLE_SCHEDULER:
        return DependencyStatus(name="scheduler", healthy=True)
    try:
        from app.agents.source_collection.scheduler import scheduler

        return DependencyStatus(name="scheduler", healthy=scheduler.running)
    except Exception:  # noqa: BLE001
        return DependencyStatus(name="scheduler", healthy=False)


def _check_disk() -> DependencyStatus:
    try:
        free = shutil.disk_usage("/").free
        return DependencyStatus(name="disk", healthy=free > _MIN_FREE_DISK_BYTES)
    except Exception:  # noqa: BLE001
        return DependencyStatus(name="disk", healthy=False)


async def get_readiness() -> ReadinessStatus:
    """Readiness: required dependencies are reachable."""
    dependencies = [
        DependencyStatus(name="database", healthy=await ping_database()),
        await _check_redis(),
        _check_scheduler(),
        _check_disk(),
    ]
    return ReadinessStatus(
        ready=all(dep.healthy for dep in dependencies),
        dependencies=dependencies,
    )
