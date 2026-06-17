#!/usr/bin/env bash
# Autogenerate a new Alembic migration from model changes.
# Usage: ./scripts/create_migration.sh "describe your change"
set -euo pipefail

cd "$(dirname "$0")/.."

MESSAGE="${1:-migration}"
alembic revision --autogenerate -m "$MESSAGE"
