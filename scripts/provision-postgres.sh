#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "provision-postgres.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

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
if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == "credential_file" \
   && ( "$database_host" != "$PGHOST" || "$database_port" != "$PGPORT" ) ]]; then
  echo "Application and provisioning connections must use the same local PostgreSQL endpoint." >&2
  exit 2
fi

echo "Provision target: host=$database_host port=$database_port database=tibiahub role=tibiahub_app"
echo "Administration mode: $TIBIAHUB_POSTGRES_ADMIN_MODE"
require_postgres_admin_access

server_version_num="$(postgres_admin_psql -X -A -t -c 'SHOW server_version_num')"
if [[ ! "$server_version_num" =~ ^[0-9]+$ || "$server_version_num" -lt 160000 ]]; then
  echo "TibiaHub requires PostgreSQL 16 or newer." >&2
  exit 2
fi
listen_addresses="$(postgres_admin_psql -X -A -t -c 'SHOW listen_addresses')"
IFS=',' read -r -a configured_addresses <<<"$listen_addresses"
for configured_address in "${configured_addresses[@]}"; do
  configured_address="${configured_address//[[:space:]]/}"
  if [[ "$configured_address" != "localhost" && "$configured_address" != "127.0.0.1" && "$configured_address" != "::1" ]]; then
    echo "PostgreSQL is not restricted to localhost; provisioning refused." >&2
    exit 2
  fi
done

if [[ ! "$TIBIAHUB_DB_PASSWORD" =~ ^[A-Za-z0-9_-]{32,}$ ]]; then
  echo "Generated TibiaHub application-role password has an unexpected format." >&2
  exit 2
fi
{
  printf "\\set role_password '%s'\n" "$TIBIAHUB_DB_PASSWORD"
  cat <<'SQL'
SELECT 'CREATE ROLE tibiahub_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tibiahub_app') \gexec
ALTER ROLE tibiahub_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'role_password';
SQL
} | postgres_admin_psql -X -v ON_ERROR_STOP=1

postgres_admin_psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE DATABASE tibiahub OWNER tibiahub_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'tibiahub') \gexec
ALTER DATABASE tibiahub OWNER TO tibiahub_app;
SQL

PGHOST="$database_host" PGPORT="$database_port" PGUSER="$application_role" \
  PGPASSWORD="$TIBIAHUB_DB_PASSWORD" PGDATABASE="$database_name" \
  psql -X -v ON_ERROR_STOP=1 <<'SQL'
REVOKE ALL ON DATABASE tibiahub FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE tibiahub TO tibiahub_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO tibiahub_app;
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
