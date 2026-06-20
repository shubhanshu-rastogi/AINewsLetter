#!/usr/bin/env bash
# Restore a PostgreSQL custom-format backup produced by backup_database.sh.
#
# Usage:
#   ./scripts/restore_database.sh <backup_file.dump>
# WARNING: drops and recreates objects in the target database.
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore_database.sh <backup_file.dump>}"
[ -f "$BACKUP_FILE" ] || { echo "Backup file not found: $BACKUP_FILE" >&2; exit 1; }

PGDATABASE="${PGDATABASE:-ainewsletter}"
PGUSER="${PGUSER:-postgres}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"

read -r -p "Restore ${BACKUP_FILE} into ${PGDATABASE}@${PGHOST}? This OVERWRITES data. [y/N] " ok
[ "$ok" = "y" ] || { echo "Aborted."; exit 1; }

echo "Restoring ${BACKUP_FILE} -> ${PGDATABASE}"
pg_restore --clean --if-exists --no-owner --no-privileges \
  --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
  --dbname="$PGDATABASE" "$BACKUP_FILE"

echo "Restore complete. Run 'alembic upgrade head' to ensure schema is current."
