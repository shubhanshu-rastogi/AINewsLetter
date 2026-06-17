#!/usr/bin/env bash
# Run the API locally with autoreload (expects a virtualenv + reachable Postgres).
set -euo pipefail

cd "$(dirname "$0")/.."

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
