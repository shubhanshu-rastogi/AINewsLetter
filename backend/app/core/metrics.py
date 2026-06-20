"""Prometheus metrics definitions and helpers."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# --- HTTP ---
REQUEST_COUNT = Counter("ainl_request_count", "Total HTTP requests", ["method", "path", "status"])
REQUEST_DURATION = Histogram("ainl_request_duration_seconds", "HTTP request duration", ["method", "path"])

# --- Workflow / agents ---
WORKFLOW_DURATION = Histogram("ainl_workflow_duration_seconds", "Workflow run duration", ["workflow"])
AGENT_DURATION = Histogram("ainl_agent_duration_seconds", "Agent execution duration", ["agent", "status"])
NEWSLETTER_GENERATION_DURATION = Histogram(
    "ainl_newsletter_generation_duration_seconds", "Newsletter generation duration"
)

# --- Publishing ---
PUBLICATION_COUNT = Counter("ainl_publication_count", "Successful publications", ["channel"])
PUBLICATION_FAILURE_COUNT = Counter("ainl_publication_failure_count", "Failed publications", ["channel", "error_type"])

# --- Scheduler / DB ---
SCHEDULER_RUNS = Counter("ainl_scheduler_runs", "Scheduler job runs", ["job"])
DATABASE_QUERY_DURATION = Histogram("ainl_database_query_duration_seconds", "Database query duration", ["operation"])

# --- Live gauges ---
ACTIVE_REVIEW_SESSIONS = Gauge("ainl_active_review_sessions", "Review sessions awaiting a decision")
RATE_LIMITED_REQUESTS = Counter("ainl_rate_limited_requests", "Requests rejected by the rate limiter", ["group"])


def render_metrics() -> tuple[bytes, str]:
    """Return (payload, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
