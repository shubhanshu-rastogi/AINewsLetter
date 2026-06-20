"""Rate limiting middleware (fixed-window, Redis-backed with in-memory fallback).

Protects the review, publish, and subscriber endpoint groups. Returns 429 with a
``Retry-After`` header when a client exceeds the limit.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import RATE_LIMITED_REQUESTS
from app.core.redis_client import get_redis

logger = get_logger("ratelimit")

# Path prefix -> rate-limit group name.
_PROTECTED_GROUPS = {
    "/api/reviews": "reviews",
    "/api/publish": "publish",
    "/api/publications": "publish",
    "/api/subscribers": "subscribers",
}


def _group_for(path: str) -> str | None:
    for prefix, group in _PROTECTED_GROUPS.items():
        if path.startswith(prefix):
            return group
    return None


def _client_id(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    return request.headers.get("X-Forwarded-For", client).split(",")[0].strip()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.ENABLE_RATE_LIMIT:
            return await call_next(request)
        group = _group_for(request.url.path)
        if group is None:
            return await call_next(request)

        window = int(time.time() // 60)
        key = f"rl:{group}:{_client_id(request)}:{window}"
        limit = settings.RATE_LIMIT_PER_MINUTE + settings.RATE_LIMIT_BURST

        redis = await get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)

        if count > limit:
            RATE_LIMITED_REQUESTS.labels(group).inc()
            logger.warning("rate_limited", group=group, client=_client_id(request), count=count)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "success": False,
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Try again later.",
                    },
                },
            )
        return await call_next(request)
