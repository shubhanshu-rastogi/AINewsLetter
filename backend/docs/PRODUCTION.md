# Production Readiness — Index

Operational documentation for the AI & Quality Engineering Weekly platform.

| Doc | Contents |
|---|---|
| [architecture_production.md](architecture_production.md) | Production architecture diagram + scaling to target volumes |
| [deployment.md](deployment.md) | Single-server / Compose / future-k8s; startup, shutdown, scaling, rollback |
| [cicd.md](cicd.md) | GitHub Actions pipeline, quality gates, PR checks |
| [monitoring.md](monitoring.md) | Structured logging, Prometheus metrics, Grafana, tracing, reports |
| [security.md](security.md) | Headers, CORS, validation, rate limiting, idempotency, auth, CSRF |
| [database_optimization.md](database_optimization.md) | Pooling, statement timeout, slow-query logging, indexes |
| [disaster_recovery.md](disaster_recovery.md) | RPO/RTO, backup/restore, app/db/workflow recovery |
| [runbook.md](runbook.md) | Day-2 operations, triage table, common procedures, escalation |
| [performance_report.md](performance_report.md) | Load-test results + capacity guidance |
| [known_risks.md](known_risks.md) | Risk register with mitigations |
| [../security/SECURITY.md](../security/SECURITY.md) | Vulnerability disclosure policy |

## Capabilities delivered
Config separation + fail-fast validation · secret provider + log masking ·
structured logging with correlation ids · Prometheus `/metrics` + Grafana
dashboards · `/health` `/health/live` `/health/ready` · Redis abstraction with
in-memory fallback · rate limiting · idempotency · security headers/CORS/size
limits · auth abstraction · workflow recovery service · DB pooling/timeouts/
slow-query logging · backup/restore + recovery scripts · load-test harness ·
production Docker Compose (API/Postgres/Redis/Prometheus/Grafana) · CI/CD with
90% coverage gate, migration verification, and security scanning.
