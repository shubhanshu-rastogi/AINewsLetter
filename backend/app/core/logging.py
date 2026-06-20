"""Structured logging configuration based on ``structlog``.

Call :func:`configure_logging` once during application startup. Use
:func:`get_logger` everywhere else to obtain a bound logger. When
``LOG_JSON`` is enabled, logs are emitted as single-line JSON (production
friendly); otherwise a colorized console renderer is used (developer friendly).
"""

from __future__ import annotations

import logging
import sys

import structlog

from app import __version__
from app.core.config import Settings
from app.core.secrets import mask_text


def _add_service_context(service: str, environment: str):
    """Processor that stamps every log line with service/environment/version."""

    def processor(_logger, _method, event_dict):
        event_dict.setdefault("service", service)
        event_dict.setdefault("environment", environment)
        event_dict.setdefault("version", __version__)
        return event_dict

    return processor


def _mask_secrets(_logger, _method, event_dict):
    """Mask secret-shaped substrings in all string values before rendering."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str) and value:
            event_dict[key] = mask_text(value)
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure ``structlog`` and the stdlib logging bridge."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_context(settings.SERVICE_NAME, settings.environment),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _mask_secrets,
    ]

    renderer = structlog.processors.JSONRenderer() if settings.LOG_JSON else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route the stdlib root logger (uvicorn, sqlalchemy, etc.) to stdout at the
    # configured level so all output is consistent.
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
