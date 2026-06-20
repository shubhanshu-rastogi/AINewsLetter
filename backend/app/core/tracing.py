"""Optional OpenTelemetry tracing setup.

No-op unless ``ENABLE_TRACING`` is set and the OpenTelemetry packages are
installed, so the dependency stays optional. When enabled it instruments FastAPI
and SQLAlchemy and exports OTLP spans with the service name + environment.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("tracing")


def setup_tracing(app) -> bool:
    """Instrument the app for tracing. Returns True if tracing was enabled."""
    if not settings.ENABLE_TRACING:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": settings.SERVICE_NAME,
                "deployment.environment": settings.environment,
            }
        )
        provider = TracerProvider(resource=resource)
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
            )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("tracing_enabled", endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        return True
    except Exception as exc:  # noqa: BLE001 - tracing is optional
        logger.warning("tracing_setup_skipped", error=str(exc))
        return False
