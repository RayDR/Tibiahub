#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "verify-postgres.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

load_tibiahub_environment
require_local_tibiahub_target
PYTHONPATH="$TIBIAHUB_BACKEND" APP_ENV="${APP_ENV:-production}" \
  "$TIBIAHUB_BACKEND/venv/bin/python" -c \
  "from app.db.database import verify_connection_and_schema; verify_connection_and_schema()"
run_alembic current
postgres_exec psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT current_database() AS database_name, current_user AS application_role;
SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent', 'postgis') ORDER BY extname;
DO $tibiahub$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')
     OR NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'unaccent') THEN
    RAISE EXCEPTION 'required TibiaHub extensions are missing';
  END IF;
END
$tibiahub$;
SELECT COUNT(*) AS expected_table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'events', 'raffles', 'sync_jobs', 'workspace_audits', 'guild_leadership_applications');
DO $tibiahub$
BEGIN
  IF (SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_name IN ('users', 'events', 'raffles', 'sync_jobs', 'workspace_audits', 'guild_leadership_applications')) <> 6 THEN
    RAISE EXCEPTION 'expected TibiaHub tables are missing';
  END IF;
END
$tibiahub$;
BEGIN;
CREATE TEMP TABLE tibiahub_verification(value integer);
INSERT INTO tibiahub_verification VALUES (1);
SELECT value FROM tibiahub_verification;
ROLLBACK;
SQL
echo "TibiaHub PostgreSQL verification passed without accessing another database."
