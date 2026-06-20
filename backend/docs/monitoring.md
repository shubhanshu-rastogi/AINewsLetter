# Monitoring & Observability

## Structured logging
JSON logs via structlog. Every line carries `timestamp`, `level`, `service`,
`environment`, `version`, plus contextual `request_id` (from
`RequestContextMiddleware`) and, where bound, `workflow_run_id`,
`newsletter_id`, `agent_name`. Secret-shaped values (URL creds, bearer tokens,
`sk-…` keys) are masked by a logging processor before render.

Key events: `application_startup`, `request_completed`, `node_started/completed/failed`,
`workflow_paused_for_review`, `workflow_resumed`, agent run events,
`beehiiv_publication_*`, `publication_failed`, `retry_scheduled`,
`scheduler_started/stopped`, `review_*`.

## Metrics (`GET /metrics`, Prometheus text)
| Metric | Type | Labels |
|---|---|---|
| `ainl_request_count` | counter | method, path, status |
| `ainl_request_duration_seconds` | histogram | method, path |
| `ainl_workflow_duration_seconds` | histogram | workflow |
| `ainl_agent_duration_seconds` | histogram | agent, status |
| `ainl_newsletter_generation_duration_seconds` | histogram | — |
| `ainl_publication_count` | counter | channel |
| `ainl_publication_failure_count` | counter | channel, error_type |
| `ainl_scheduler_runs` | counter | job |
| `ainl_database_query_duration_seconds` | histogram | operation |
| `ainl_active_review_sessions` | gauge | — |
| `ainl_rate_limited_requests` | counter | group |

Prometheus scrape config: `monitoring/prometheus.yml`.

## Grafana
Auto-provisioned datasource + dashboards from `monitoring/grafana/provisioning`.
The **Platform Overview** dashboard (`monitoring/grafana/dashboards/platform_overview.json`)
has rows for the required categories:
- **Application Health** — request rate, p95 latency
- **Workflow Health** — workflow/agent p95 duration, active review sessions
- **Newsletter Metrics** — generation p95 duration
- **Publication Metrics** — success vs failure by channel
- **Infrastructure** — DB query p95, rate-limited requests

## Tracing (optional)
Set `ENABLE_TRACING=true` and install the OpenTelemetry extras (commented in
`requirements.txt`). `app/core/tracing.py` instruments FastAPI and exports OTLP
to `OTEL_EXPORTER_OTLP_ENDPOINT`. The `request_id` correlation id ties logs,
metrics, and traces together.

## Operational reports (from metrics + DB)
- workflow / newsletter-generation durations → histogram p50/p95/p99
- agent failures → `ainl_agent_duration_seconds_count{status="failed"}`
- publication success rate → `count / (count + failure_count)` per channel
- review turnaround → `review_versions` / `review_sessions` timestamps
- subscriber growth → `GET /api/subscribers/stats` over time
