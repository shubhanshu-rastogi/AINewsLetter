#!/usr/bin/env bash
set -euo pipefail

# Apply database migrations before starting the application.
# Safe to run on every boot - Alembic is idempotent (no-op when up to date).
echo "Running database migrations..."
alembic upgrade head || echo "WARNING: alembic upgrade failed (no migrations yet?). Continuing."

echo "Starting application..."
exec "$@"
