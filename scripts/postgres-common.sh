#!/usr/bin/env bash
set -Eeuo pipefail

TIBIAHUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIBIAHUB_BACKEND="$TIBIAHUB_ROOT/backend"
TIBIAHUB_RUNTIME_SECRETS_FILE="${TIBIAHUB_SECRETS_FILE:-/forge/tibiahub-secrets/runtime.env}"
TIBIAHUB_PROVISION_SECRETS_FILE="${TIBIAHUB_PROVISION_SECRETS_FILE:-/forge/tibiahub-secrets/provision.env}"

load_secure_file() {
  local secret_path="$1"
  local description="$2"
  local mode
  local owner
  local directory_mode
  local directory_owner
  if [[ "$secret_path" != /* || ! -f "$secret_path" || -L "$secret_path" ]]; then
    echo "$description must be an absolute, regular, non-symlink file: $secret_path" >&2
    exit 2
  fi
  mode="$(stat -c '%a' "$secret_path")"
  owner="$(stat -c '%u' "$secret_path")"
  directory_mode="$(stat -c '%a' "$(dirname "$secret_path")")"
  directory_owner="$(stat -c '%u' "$(dirname "$secret_path")")"
  if [[ "$owner" != "$(id -u)" || $((8#$mode & 077)) -ne 0 ]]; then
    echo "$description must be owned by the service user and inaccessible to group/other." >&2
    exit 2
  fi
  if [[ "$directory_owner" != "$(id -u)" || $((8#$directory_mode & 077)) -ne 0 ]]; then
    echo "$description directory must be owned by the service user and inaccessible to group/other." >&2
    exit 2
  fi
  # shellcheck disable=SC1090
  set -a
  source "$secret_path"
  set +a
}

load_tibiahub_environment() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    load_secure_file "$TIBIAHUB_RUNTIME_SECRETS_FILE" "TibiaHub runtime secret file"
  fi
  : "${DATABASE_URL:?DATABASE_URL must be set in the environment or external runtime secret file}"
}

load_postgres_admin_environment() {
  load_secure_file "$TIBIAHUB_PROVISION_SECRETS_FILE" "TibiaHub provisioning secret file"
  : "${TIBIAHUB_POSTGRES_ADMIN_MODE:?TIBIAHUB_POSTGRES_ADMIN_MODE must explicitly select peer or credential_file}"
  : "${TIBIAHUB_DB_PASSWORD:?TIBIAHUB_DB_PASSWORD is required in the provisioning secret file}"
  case "$TIBIAHUB_POSTGRES_ADMIN_MODE" in
    peer)
      ;;
    credential_file)
      : "${PGHOST:?PGHOST is required in credential_file mode}"
      : "${PGPORT:?PGPORT is required in credential_file mode}"
      : "${PGDATABASE:?PGDATABASE is required in credential_file mode}"
      : "${PGUSER:?PGUSER is required in credential_file mode}"
      : "${PGPASSWORD:?PGPASSWORD is required in credential_file mode}"
      if [[ "$PGHOST" != "127.0.0.1" && "$PGHOST" != "localhost" && "$PGHOST" != "::1" ]]; then
        echo "Provisioning administrator connectivity must remain localhost-only." >&2
        exit 2
      fi
      if [[ "$PGDATABASE" != "postgres" ]]; then
        echo "Provisioning administrator maintenance database must be exactly postgres." >&2
        exit 2
      fi
      ;;
    *)
      echo "Unsupported TIBIAHUB_POSTGRES_ADMIN_MODE; use peer or credential_file." >&2
      exit 2
      ;;
  esac
}

postgres_admin_psql() {
  if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == "peer" ]]; then
    sudo -n -u postgres psql -p "${TIBIAHUB_DATABASE_PORT:-5432}" -d postgres "$@"
  else
    psql "$@"
  fi
}

postgres_admin_createdb() {
  if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == "peer" ]]; then
    sudo -n -u postgres createdb -p "${TIBIAHUB_DATABASE_PORT:-5432}" "$@"
  else
    createdb "$@"
  fi
}

postgres_admin_dropdb() {
  if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == "peer" ]]; then
    sudo -n -u postgres dropdb -p "${TIBIAHUB_DATABASE_PORT:-5432}" "$@"
  else
    dropdb "$@"
  fi
}

require_postgres_admin_access() {
  if ! postgres_admin_psql -X -A -t -c 'SELECT 1' >/dev/null; then
    if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == "peer" ]]; then
      echo "Peer administration was selected, but passwordless sudo access to local postgres is unavailable; no fallback was attempted." >&2
    else
      echo "Credential-file PostgreSQL administration failed; no peer fallback was attempted." >&2
    fi
    exit 2
  fi
}

database_component() {
  APP_ENV="${APP_ENV:-production}" PYTHONPATH="$TIBIAHUB_BACKEND" \
    "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/postgres-target.py" "$1"
}

postgres_exec() {
  PYTHONPATH="$TIBIAHUB_BACKEND" APP_ENV="${APP_ENV:-production}" \
    "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/postgres-command.py" "$@"
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
