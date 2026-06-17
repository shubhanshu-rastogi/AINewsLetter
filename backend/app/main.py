"""FastAPI application factory and entry point.

Wires together configuration, logging, middleware, exception handling, routers,
and startup/shutdown lifecycle. Run with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.api.workflows import router as workflows_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware

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
    yield
    # ---- shutdown ----
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

    # Middleware
    app.add_middleware(RequestContextMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(workflows_router, prefix="/api/workflows")

    return app


app = create_app()
