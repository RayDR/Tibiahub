#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/postgres-common.sh"

if [[ "${1:-}" != "--confirm-provision-tibiahub" || $# -ne 1 ]]; then
  echo "Usage: $0 --confirm-provision-tibiahub" >&2
  exit 2
fi

load_postgres_admin_environment

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
if [[ "$database_host" != "$PGHOST" || "$database_port" != "$PGPORT" ]]; then
  echo "Application and provisioning connections must use the same local PostgreSQL endpoint." >&2
  exit 2
fi

echo "Provision target: host=$database_host port=$database_port database=tibiahub role=tibiahub_app"

server_version_num="$(psql -X -A -t -c 'SHOW server_version_num')"
if [[ ! "$server_version_num" =~ ^[0-9]+$ || "$server_version_num" -lt 160000 ]]; then
  echo "TibiaHub requires PostgreSQL 16 or newer." >&2
  exit 2
fi
listen_addresses="$(psql -X -A -t -c 'SHOW listen_addresses')"
IFS=',' read -r -a configured_addresses <<<"$listen_addresses"
for configured_address in "${configured_addresses[@]}"; do
  configured_address="${configured_address//[[:space:]]/}"
  if [[ "$configured_address" != "localhost" && "$configured_address" != "127.0.0.1" && "$configured_address" != "::1" ]]; then
    echo "PostgreSQL is not restricted to localhost; provisioning refused." >&2
    exit 2
  fi
done

export TIBIAHUB_DATABASE_ROLE="$application_role"
export TIBIAHUB_DATABASE_NAME="$database_name"
psql -X -v ON_ERROR_STOP=1 <<'SQL'
\getenv role_name TIBIAHUB_DATABASE_ROLE
\getenv role_password TIBIAHUB_DB_PASSWORD
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role_name', :'role_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role_name') \gexec
SELECT format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'role_name', :'role_password') \gexec
SQL

psql -X -v ON_ERROR_STOP=1 <<'SQL'
\getenv db_name TIBIAHUB_DATABASE_NAME
\getenv role_name TIBIAHUB_DATABASE_ROLE
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'role_name')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'role_name') \gexec
SQL

PGHOST="$database_host" PGPORT="$database_port" PGUSER="$application_role" \
  PGPASSWORD="$TIBIAHUB_DB_PASSWORD" PGDATABASE="$database_name" \
  psql -X -v ON_ERROR_STOP=1 <<'SQL'
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
