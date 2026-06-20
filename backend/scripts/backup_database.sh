#!/usr/bin/env bash
# PostgreSQL logical backup (custom format, compressed).
#
# Usage:
#   ./scripts/backup_database.sh [output_dir]
# Env: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE  (or DATABASE_URL)
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

PGDATABASE="${PGDATABASE:-ainewsletter}"
PGUSER="${PGUSER:-postgres}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/ainewsletter_${TS}.dump"

echo "Backing up ${PGDATABASE}@${PGHOST}:${PGPORT} -> ${OUT_FILE}"
pg_dump --format=custom --no-owner --no-privileges \
  --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
  --dbname="$PGDATABASE" --file="$OUT_FILE"

# Retain only the 14 most recent backups.
ls -1t "${OUT_DIR}"/ainewsletter_*.dump 2>/dev/null | tail -n +15 | xargs -r rm -f

echo "Backup complete: ${OUT_FILE} ($(du -h "$OUT_FILE" | cut -f1))"
