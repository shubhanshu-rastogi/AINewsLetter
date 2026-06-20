# Disaster Recovery

## Targets
| Metric | Target | Basis |
|---|---|---|
| **RPO** (max data loss) | ≤ 24h (default) / ≤ 1h with WAL archiving | nightly `pg_dump` + optional PITR |
| **RTO** (max downtime) | ≤ 1h single-server restore; ≤ 15m with warm standby | restore from latest dump + `alembic upgrade head` |

## Backups
- Nightly logical backup: `scripts/backup_database.sh` (pg_dump custom format,
  14-backup retention). Schedule via cron/systemd-timer or the orchestrator.
- For tighter RPO, enable PostgreSQL WAL archiving / a managed PITR-capable DB.
- Store backups off-host (object storage) with encryption at rest.

## Recovery procedures

### 1. Application restart
```bash
docker compose -f docker-compose.prod.yml restart api
# verify
curl -fsS localhost:8000/health/ready
```
Paused review workflows and human-review state are durable in Postgres, so they
survive restarts. After restart, run workflow recovery (below).

### 2. Database recovery
```bash
# Provision a fresh Postgres, then:
PGHOST=... PGUSER=... PGDATABASE=ainewsletter \
  ./scripts/restore_database.sh backups/ainewsletter_<ts>.dump
# Bring schema to head (no-op if backup was current):
alembic upgrade head
# Point the app at the restored DB and restart.
```

### 3. Workflow recovery (after an incident/restart)
```bash
python -m scripts.recover
```
`WorkflowRecoveryService.recover_all()`:
- lists **paused review workflows** (awaiting human action)
- **drains the publication retry queue** (re-attempts failed channels; abandons at max retries)
- marks **interrupted (stuck RUNNING) workflow + agent runs** as failed so they can be re-run
- ensures the **scheduler** is running

## Drill checklist
1. Restore last night's dump into a scratch DB; run `alembic check`.
2. Boot the app against it; confirm `/health/ready` is 200.
3. Run `python -m scripts.recover`; confirm summary counts are sane.
4. Record actual RTO; compare to target.
