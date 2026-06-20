# Agentic AI Newsletter Platform — Backend

Backend for the Agentic AI Newsletter Platform: a LangGraph workflow of **12
specialized agents** that collects sources, filters/categorizes them,
fact-checks claims, writes the newsletter (+ LinkedIn post), generates visuals,
runs an editorial pass, **pauses for human review**, processes feedback, and
publishes to Beehiiv / LinkedIn / email.

> 👉 **Start here:** the top-level [`../README.md`](../README.md) is the full
> getting-started guide — pipeline overview, end-to-end usage walkthrough, and
> the complete **API-keys / configuration** reference.
> System design: [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ·
> Operations: [`docs/PRODUCTION.md`](docs/PRODUCTION.md)

## Tech stack

Python 3.12 · FastAPI · LangGraph · SQLAlchemy 2.0 (async) · asyncpg · Alembic ·
PostgreSQL · Pydantic v2 · structlog · Redis (optional) · APScheduler ·
Prometheus · Pillow · Docker / Compose. Anthropic / OpenAI / Beehiiv / LinkedIn /
Notion integrations are used only when their `ENABLE_*` flags are turned on.

## Repository layout

```
backend/
├── app/
│   ├── api/            # HTTP layer: health, workflows, sources, articles,
│   │                   #   facts, newsletters, visuals, reviews, publishing,
│   │                   #   publications, subscribers, versioned v1 router
│   ├── core/           # config, logging, secrets, exceptions
│   ├── db/             # async engine/session, base metadata, seed
│   ├── models/         # SQLAlchemy ORM models + enums
│   ├── schemas/        # Pydantic request/response models
│   ├── services/       # business/service layer
│   ├── repositories/   # data-access layer
│   ├── agents/         # the 12 agents (source_collection, relevance_filter,
│   │                   #   categorization, fact_checking, newsletter_writer,
│   │                   #   visual_generation, review_feedback, publishing)
│   ├── workflows/      # LangGraph state, nodes, graph, service
│   ├── middleware/     # request context, errors, rate limit, idempotency
│   ├── utils/          # helpers
│   └── main.py         # FastAPI app factory + lifespan + router mounts
├── alembic/            # migration environment + versions
├── tests/              # pytest suite (runs offline, ~230 tests)
├── docker/             # container entrypoint
├── scripts/            # seed, run_local, migrations, backup/restore, recover, load_test
├── docs/               # developer + production docs
├── Dockerfile
├── docker-compose.yml / docker-compose.prod.yml
├── requirements.txt / requirements-dev.txt
└── .env.example
```

## Quick start (Docker)

```bash
cp .env.example .env            # defaults run offline, no keys needed
docker compose up --build
docker compose exec api python -m scripts.seed       # categories, admin, settings
curl -X POST http://localhost:8000/api/sources/seed  # curated content sources
```

API docs at http://localhost:8000/docs. The `api` container runs `alembic
upgrade head` on boot, then starts Uvicorn.

## Quick start (local Python)

Requires Python 3.12 and a reachable PostgreSQL instance.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set POSTGRES_HOST=localhost
alembic upgrade head
python -m scripts.seed                              # categories, admin, settings
uvicorn app.main:app --reload                       # or: bash scripts/run_local.sh
# then seed sources: curl -X POST http://localhost:8000/api/sources/seed
```

## Running tests

```bash
pip install -r requirements-dev.txt
pytest                          # full suite — offline, uses SQLite
ruff check app tests scripts    # lint
```

All `ENABLE_*` flags are forced off in tests, so no network/API keys are
required. CI enforces a 90% coverage gate (see [`docs/cicd.md`](docs/cicd.md)).

## Configuration

All settings come from environment variables (or `.env`). The annotated list is
in [`.env.example`](.env.example); the authoritative schema is
[`app/core/config.py`](app/core/config.py). For the full explanation of which
API key unlocks which feature flag, see the root [`../README.md`](../README.md).
