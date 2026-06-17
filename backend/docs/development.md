# Development Notes

This backend is the **foundation phase** of the Agentic AI Newsletter Platform.
It deliberately contains **no** agent logic, newsletter generation, or external
API integrations yet — only the platform skeleton.

See the system design in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).

## What exists today

- FastAPI app factory with structured logging, request-context middleware, and
  centralized error handling.
- Async SQLAlchemy + asyncpg connection layer with a dependency-injected session.
- Alembic (async) wired to application settings and model metadata.
- Placeholder ORM models: User, Source, Article, Newsletter, NewsletterSection,
  Feedback, Publication.
- `/health` (liveness) and `/ready` (readiness) probes.
- Generic async base repository.
- Pytest setup with a database-free health-check test.

## What is intentionally NOT implemented

- Agent logic (`app/agents/` has only a `BaseAgent` interface).
- LangGraph workflow (`app/workflows/` has only state + a stub builder).
- Beehiiv / LinkedIn / Notion integrations.
- Business rules on models and services.

## Adding a migration

```bash
# after editing models
./scripts/create_migration.sh "add x to y"
alembic upgrade head
```
