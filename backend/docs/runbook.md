# Operational Runbook

## Daily / weekly cadence
- **Daily 08:00 UTC** — scheduled source collection (APScheduler).
- **Friday 06:00 UTC** — weekly newsletter workflow starts; pauses at human
  review. A reviewer must approve before publishing.

## Health & triage
| Symptom | Check | Action |
|---|---|---|
| LB marking instance down | `GET /health/ready` | inspect `dependencies[]` — db/redis/scheduler/disk |
| 5xx spike | Grafana request panel; logs by `request_id` | identify failing route; check DB/Redis |
| Workflows stuck | `ainl_active_review_sessions`; `workflow_runs` table | `python -m scripts.recover` |
| Publications failing | `ainl_publication_failure_count`; `publication_failures` | inspect error_type; `POST /api/publications/{id}/retry` or drain via recover |
| Rate-limit complaints | `ainl_rate_limited_requests` | adjust `RATE_LIMIT_PER_MINUTE` / investigate abuse |

## Common procedures
- **Trigger a newsletter run manually**: `POST /api/workflows/newsletter/start`
- **Approve / reject in review**: `POST /api/reviews/{id}/approve|reject`
- **Submit feedback (targeted regen)**: `POST /api/reviews/{id}/feedback`
- **Publish after approval**: `POST /api/publish/{newsletter_id}` (or via the workflow)
- **Retry a failed publication**: `POST /api/publications/{publication_id}/retry`
- **Recover after incident**: `python -m scripts.recover`
- **Backup now**: `./scripts/backup_database.sh`
- **Apply migrations**: `alembic upgrade head` (entrypoint does this on boot)

## Deploy / rollback
See `docs/deployment.md`. Always run `alembic upgrade head` after deploying a
release that adds a migration; use expand→contract for zero-downtime.

## Escalation
1. Page on: `/health/ready` failing across all replicas, DB unreachable, or
   publication success rate < 80% over 15m.
2. Mitigate: scale replicas, restart API, run recovery, restore DB if corrupt.
3. Post-incident: capture timeline from `run_event`/`agent_runs` + logs by
   `request_id`/`workflow_run_id`.
