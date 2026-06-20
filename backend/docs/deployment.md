# Deployment Guide

## Environments

Config is layered: base `.env` then `.env.<environment>` (`development` | `test`
| `staging` | `production`), selected by `APP_ENV`. Startup **fails fast**
(`ConfigurationError`) if required settings are missing in staging/production
(SECRET_KEY, strong POSTGRES_PASSWORD, non-wildcard CORS_ORIGINS, etc.).

Secrets are **never committed** — inject them via the deployment environment or a
secret manager (see `app/core/secrets.py` `SecretProvider`).

## Single server (Docker Compose)

```bash
cd backend
cp .env.production .env            # then inject real secrets into the environment
export POSTGRES_PASSWORD=...  SECRET_KEY=...  # required
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api python -m scripts.seed
```

Services & ports: API `:8000`, Postgres `:5432`, Redis `:6379`,
Prometheus `:9090`, Grafana `:3000`.

### Startup
1. `db` and `redis` start and must report healthy.
2. `api` runs `alembic upgrade head` (entrypoint) then `uvicorn`.
3. LB/orchestrator marks the instance in-service once `/health/ready` is 200.

### Shutdown (graceful)
```bash
docker compose -f docker-compose.prod.yml stop api   # drain; lifespan stops scheduler, disposes pool
docker compose -f docker-compose.prod.yml down       # full teardown (volumes persist)
```

### Scaling
- API is stateless: `deploy.replicas` (compose) or more pods (k8s). Put them behind the LB.
- Run **one** scheduler leader (`ENABLE_SCHEDULER=true` on a single instance/worker; `false` on the rest).
- Scale Postgres reads with replicas; Redis is shared across replicas.

### Rollback
```bash
# Roll the image back
docker compose -f docker-compose.prod.yml up -d --no-deps api   # with previous image tag
# Roll a schema change back (only if the new release shipped a migration)
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1
```
Migrations are additive/reversible; prefer expand-then-contract so app vN and
vN+1 both run against the same schema during a rollout.

## Future: Kubernetes

The stateless API maps to a `Deployment` + `HorizontalPodAutoscaler`, with:
- `livenessProbe` → `GET /health/live`, `readinessProbe` → `GET /health/ready`
- scheduler as a separate single-replica `Deployment` (leader)
- background execution as a worker `Deployment`
- Postgres/Redis as managed services or operators; secrets via `Secret`/external-secrets
- Prometheus `ServiceMonitor` scraping `/metrics`

Manifests are not included (out of scope) — see `deployments/` for the placeholder.
