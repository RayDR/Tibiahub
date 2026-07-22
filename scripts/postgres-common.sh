#!/usr/bin/env bash
set -Eeuo pipefail

TIBIAHUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIBIAHUB_BACKEND="$TIBIAHUB_ROOT/backend"

load_tibiahub_environment() {
  if [[ -z "${DATABASE_URL:-}" && -f "$TIBIAHUB_BACKEND/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$TIBIAHUB_BACKEND/.env"
    set +a
  fi
  : "${DATABASE_URL:?DATABASE_URL must be set in the environment or backend/.env}"
}

database_component() {
  APP_ENV="${APP_ENV:-production}" PYTHONPATH="$TIBIAHUB_BACKEND" \
    "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/postgres-target.py" "$1"
}

libpq_url() {
  local value="$1"
  value="${value/postgresql+psycopg2:/postgresql:}"
  value="${value/postgresql+psycopg:/postgresql:}"
  printf '%s' "$value"
}

require_local_tibiahub_target() {
  local expected_name="${TIBIAHUB_DATABASE_NAME:-tibiahub}"
  local actual_name
  local actual_host
  actual_name="$(database_component name)"
  actual_host="$(database_component host)"
  if [[ -z "$expected_name" || "$expected_name" == *"*"* || "$expected_name" == *"?"* ]]; then
    echo "Refusing blank or wildcard TibiaHub database name." >&2
    exit 2
  fi
  if [[ "$actual_name" != "$expected_name" ]]; then
    echo "Refusing database target: DATABASE_URL name does not match TIBIAHUB_DATABASE_NAME." >&2
    exit 2
  fi
  if [[ "$actual_host" != "127.0.0.1" && "$actual_host" != "localhost" && "$actual_host" != "::1" ]]; then
    echo "Refusing non-local PostgreSQL target." >&2
    exit 2
  fi
  if [[ "$(database_component dialect)" != "postgresql" ]]; then
    echo "Refusing non-PostgreSQL target." >&2
    exit 2
  fi
}

run_alembic() {
  (cd "$TIBIAHUB_BACKEND" && APP_ENV="${APP_ENV:-production}" venv/bin/alembic -c alembic.ini "$@")
}
