"""Idempotency middleware.

When a mutating request to a protected group carries an ``Idempotency-Key``
header, the first response is cached and replayed for duplicate requests -
preventing duplicate publications, resumes, review submissions, and retries.
"""

from __future__ import annotations

import base64
import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis

logger = get_logger("idempotency")

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_PROTECTED_PREFIXES = ("/api/reviews", "/api/publish", "/api/publications", "/api/subscribers")
_HEADER = "Idempotency-Key"


def _applies(request: Request) -> bool:
    if request.method not in _MUTATING:
        return False
    if _HEADER.lower() not in (h.lower() for h in request.headers):
        return False
    return request.url.path.startswith(_PROTECTED_PREFIXES)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.ENABLE_IDEMPOTENCY or not _applies(request):
            return await call_next(request)

        idem_key = request.headers[_HEADER]
        cache_key = f"idem:{request.method}:{request.url.path}:{idem_key}"
        redis = await get_redis()

        cached = await redis.get(cache_key)
        if cached:
            payload = json.loads(cached)
            logger.info("idempotent_replay", key=idem_key, path=request.url.path)
            return Response(
                content=base64.b64decode(payload["body"]),
                status_code=payload["status"],
                media_type=payload.get("media_type"),
                headers={"Idempotency-Replayed": "true"},
            )

        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        # Only cache successful, non-server-error responses.
        if response.status_code < 500:
            await redis.set(
                cache_key,
                json.dumps(
                    {
                        "status": response.status_code,
                        "body": base64.b64encode(body).decode(),
                        "media_type": response.media_type,
                    }
                ),
                ex=settings.IDEMPOTENCY_TTL_SECONDS,
            )
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=dict(response.headers),
        )
