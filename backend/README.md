# Agentic AI Newsletter Platform — Backend

Production-grade **foundation** for the Agentic AI Newsletter Platform. This
phase delivers the platform skeleton only: app bootstrap, configuration,
logging, database layer, migrations, health probes, and the base patterns that
agents and integrations will build on later.

> System design: [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

## Tech Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Alembic ·
PostgreSQL · Pydantic v2 · structlog · Docker / Docker Compose ·
LangGraph, OpenAI & Anthropic SDKs (installed; logic deferred).

## Repository Layout

```
backend/
├── app/
│   ├── api/            # HTTP layer: health probes + versioned (v1) router
│   ├── core/           # config, logging, exceptions (cross-cutting)
│   ├── db/             # SQLAlchemy base, async engine/session, metadata
│   ├── models/         # ORM models (placeholders)
│   ├── schemas/        # Pydantic request/response models
│   ├── services/       # business/service layer (health only for now)
│   ├── repositories/   # data-access layer (generic base repository)
│   ├── agents/         # agent interfaces (no logic yet)
│   ├── workflows/      # LangGraph state + graph stub (no logic yet)
│   ├── middleware/     # request context + error handling
│   ├── utils/          # small helpers
│   └── main.py         # FastAPI app factory + lifespan
├── alembic/            # migration environment + versions
├── tests/              # pytest suite
├── docker/             # container entrypoint
├── scripts/            # dev helper scripts
├── docs/               # developer docs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick Start (Docker — recommended)

```bash
cd backend
cp .env.example .env            # adjust values as needed
docker compose up --build
```

Then:

- API docs:        http://localhost:8000/docs
- Liveness:        http://localhost:8000/health
- Readiness:       http://localhost:8000/ready
- API v1 root:     http://localhost:8000/api/v1/

The `api` container runs `alembic upgrade head` on boot, then starts uvicorn.
Postgres is started first and the API waits for it to be healthy.

## Quick Start (local Python)

Requires Python 3.12 and a reachable PostgreSQL instance.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env            # set POSTGRES_HOST=localhost

# apply the schema (initial migration is already committed)
alembic upgrade head

# seed reference data (idempotent: categories, admin user, system settings)
python -m scripts.seed

# run
uvicorn app.main:app --reload
```

## Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The included health-check test does **not** require a database.

## Configuration

All settings come from environment variables (or `.env`). See
[`.env.example`](.env.example). The async database URL is derived from the
`POSTGRES_*` variables in `app/core/config.py`.

## Status

Foundation only. Agent logic, the LangGraph workflow, and external integrations
(Beehiiv / LinkedIn / Notion) are deferred to later phases.
```
