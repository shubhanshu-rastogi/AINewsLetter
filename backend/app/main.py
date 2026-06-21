"""FastAPI application factory and entry point.

Wires together configuration, logging, middleware, exception handling, routers,
and startup/shutdown lifecycle. Run with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.articles import router as articles_router
from app.api.auth import router as auth_router
from app.api.facts import router as facts_router
from app.api.health import router as health_router
from app.api.newsletters import router as newsletters_router
from app.api.publishing import publications_router, publish_router
from app.api.reviews import router as reviews_router
from app.api.settings import router as settings_router
from app.api.sources import router as sources_router
from app.api.subscribers import router as subscribers_router
from app.api.v1.router import api_router
from app.api.visuals import router as visuals_router
from app.api.workflows import router as workflows_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine
from app.middleware.error_handler import register_exception_handlers
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.observability import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security import RequestSizeLimitMiddleware, SecurityHeadersMiddleware

logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ---- startup ----
    logger.info(
        "application_startup",
        app=settings.APP_NAME,
        version=__version__,
        environment=settings.APP_ENV,
    )
    # Load any UI-managed configuration persisted in the database over the
    # environment defaults so agents pick up keys/flags set via the UI.
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.runtime_config import load_into_settings

        async with AsyncSessionLocal() as session:
            await load_into_settings(session)
    except Exception as exc:  # pragma: no cover - never block startup on config load
        logger.warning("runtime_config_load_failed", error=str(exc))

    if settings.ENABLE_SCHEDULER:
        from app.agents.source_collection.scheduler import scheduler

        scheduler.start()
    yield
    # ---- shutdown ----
    if settings.ENABLE_SCHEDULER:
        from app.agents.source_collection.scheduler import scheduler

        scheduler.shutdown()
    await dispose_engine()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging(settings)

    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware (added last = outermost). RequestContext is outermost so a
    # request_id is bound for every downstream layer.
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # Optional OpenTelemetry instrumentation (no-op unless enabled + installed).
    from app.core.tracing import setup_tracing

    setup_tracing(app)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(workflows_router, prefix="/api/workflows")
    app.include_router(sources_router, prefix="/api/sources")
    app.include_router(articles_router, prefix="/api/articles")
    app.include_router(facts_router, prefix="/api/facts")
    app.include_router(newsletters_router, prefix="/api/newsletters")
    app.include_router(visuals_router, prefix="/api/visuals")
    app.include_router(reviews_router, prefix="/api/reviews")
    app.include_router(publish_router, prefix="/api/publish")
    app.include_router(publications_router, prefix="/api/publications")
    app.include_router(subscribers_router, prefix="/api/subscribers")

    return app


app = create_app()
