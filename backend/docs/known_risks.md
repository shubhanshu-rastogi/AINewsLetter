# Known Risks

| # | Risk | Impact | Mitigation / Status |
|---|---|---|---|
| 1 | **`issue_number` race** under concurrent newsletter generation (unique-constraint collisions) | Failed generations when run in parallel | Low real-world risk (weekly, low-concurrency). Fix: Postgres sequence or retry-on-conflict. Documented in `performance_report.md` |
| 2 | **LangGraph checkpointer is in-process** (`MemorySaver`) | Paused workflows don't survive across multiple processes / restarts in their in-memory form | Human-review state is persisted in Postgres (recoverable). Switch to the Postgres LangGraph checkpointer for multi-process durability |
| 3 | **APScheduler runs per-process** | Duplicate weekly runs if multiple replicas enable the scheduler | Run a single scheduler leader (`ENABLE_SCHEDULER=true` on one instance only) |
| 4 | **Publish/subscriber endpoints unauthenticated** | Unauthorized publish/subscribe calls | `AuthProvider` abstraction in place; add `require_reviewer`/RBAC before production |
| 5 | **Retry queue is persisted but not auto-drained** | Failed publications wait for manual/recovery drain | `POST /api/publications/{id}/retry` + `scripts/recover.py`; add a scheduled drainer |
| 6 | **Email is prepare-only** | No actual delivery | Interface ready (`email_preparer`); wire an ESP/SMTP provider |
| 7 | **mypy advisory, not blocking** | Type regressions could slip in | Stub langgraph/sqlalchemy friction, then make blocking |
| 8 | **External APIs simulated by default** (`ENABLE_REAL_PUBLISHING=false`, `ENABLE_AI_IMAGES=false`) | No real external calls until enabled | Enable per-environment with keys; real paths are mock-tested |
| 9 | **RPO up to 24h** with nightly dumps only | Data loss window | Enable WAL archiving/PITR or a managed DB for ≤1h RPO |
| 10 | **No automated DB partitioning** | Table bloat at multi-year scale | Documented partitioning plan in `database_optimization.md`; implement before 10M+ rows |
