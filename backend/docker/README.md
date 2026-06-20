# Docker

- **`../Dockerfile`** — multi-stage, non-root (`appuser`), `HEALTHCHECK` on
  `/health`, entrypoint runs `alembic upgrade head` then Uvicorn.
- **`../docker-compose.yml`** — dev stack (Postgres + API).
- **`../docker-compose.prod.yml`** — prod stack (API ×2, Postgres, Redis,
  Prometheus, Grafana) with health checks and named volumes.
- **`entrypoint.sh`** — migrate-then-serve.

Build & run: see `docs/deployment.md`.
