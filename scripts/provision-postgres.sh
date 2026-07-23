#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/postgres-common.sh"

if [[ "${1:-}" != "--confirm-provision-tibiahub" || $# -ne 1 ]]; then
  echo "Usage: $0 --confirm-provision-tibiahub" >&2
  exit 2
fi

: "${POSTGRES_ADMIN_URL:?POSTGRES_ADMIN_URL must identify an elevated local PostgreSQL role}"
: "${TIBIAHUB_DB_PASSWORD:?TIBIAHUB_DB_PASSWORD is required and will not be printed}"

database_name="${TIBIAHUB_DATABASE_NAME:-tibiahub}"
application_role="${TIBIAHUB_DATABASE_ROLE:-tibiahub_app}"
database_host="${TIBIAHUB_DATABASE_HOST:-127.0.0.1}"
database_port="${TIBIAHUB_DATABASE_PORT:-5432}"

if [[ "$database_name" != "tibiahub" || "$application_role" != "tibiahub_app" ]]; then
  echo "Provisioning is restricted to database tibiahub and role tibiahub_app." >&2
  exit 2
fi
if [[ "$database_host" != "127.0.0.1" && "$database_host" != "localhost" && "$database_host" != "::1" ]]; then
  echo "Provisioning is restricted to localhost PostgreSQL." >&2
  exit 2
fi

psql "$(libpq_url "$POSTGRES_ADMIN_URL")" -X -v ON_ERROR_STOP=1 -v role_name="$application_role" -v role_password="$TIBIAHUB_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role_name', :'role_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role_name') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'role_name', :'role_password') \gexec
SQL

psql "$(libpq_url "$POSTGRES_ADMIN_URL")" -X -v ON_ERROR_STOP=1 -v db_name="$database_name" -v role_name="$application_role" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'role_name')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
SQL

PGPASSWORD="$TIBIAHUB_DB_PASSWORD" psql -X -h "$database_host" -p "$database_port" -U "$application_role" -d "$database_name" -v ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
DO $tibiahub$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') THEN
    BEGIN
      CREATE EXTENSION IF NOT EXISTS postgis;
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'PostGIS requires elevated installation privileges';
    END;
  END IF;
END
$tibiahub$;
SQL

echo "Provisioned local database tibiahub and role tibiahub_app. Run Alembic manually before service startup."
