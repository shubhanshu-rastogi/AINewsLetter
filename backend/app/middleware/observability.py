"""Prometheus metrics middleware."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import REQUEST_COUNT, REQUEST_DURATION


def _route_template(request: Request) -> str:
    """Use the matched route template to keep metric label cardinality low."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        path = _route_template(request)
        REQUEST_DURATION.labels(request.method, path).observe(time.perf_counter() - start)
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        return response
