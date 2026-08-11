#!/usr/bin/env bash

# Shared PostgreSQL and Alembic operational helpers.
# This file is intended to be sourced by entrypoint scripts.

if [[ "${_TIBIAHUB_POSTGRES_LIB_LOADED:-0}" == "1" ]]; then
  return 0
fi
_TIBIAHUB_POSTGRES_LIB_LOADED=1

TIBIAHUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIBIAHUB_BACKEND="$TIBIAHUB_ROOT/backend"
TIBIAHUB_RUNTIME_SECRETS_FILE="${TIBIAHUB_SECRETS_FILE:-/forge/tibiahub-secrets/runtime.env}"
TIBIAHUB_PROVISION_SECRETS_FILE="${TIBIAHUB_PROVISION_SECRETS_FILE:-/forge/tibiahub-secrets/provision.env}"

_tibiahub_env_loaded="${_TIBIAHUB_RUNTIME_ENV_LOADED:-0}"
_tibiahub_admin_env_loaded="${_TIBIAHUB_ADMIN_ENV_LOADED:-0}"


tibiahub_runtime_dir() {
  local requested="${TIBIAHUB_PYTHON_RUNTIME:-}"

  if [[ -n "$requested" ]]; then
    [[ "$requested" == /* ]] || {
      postgres_fail "TIBIAHUB_PYTHON_RUNTIME must be absolute."
      return $?
    }
    [[ -x "$requested/bin/python" ]] || {
      postgres_fail "Configured TibiaHub Python runtime is unavailable."
      return $?
    }
    printf '%s\n' "$requested"
    return 0
  fi

  if [[ -x "$TIBIAHUB_BACKEND/runtime-current/bin/python" ]]; then
    printf '%s\n' "$TIBIAHUB_BACKEND/runtime-current"
    return 0
  fi

  [[ -x "$TIBIAHUB_BACKEND/venv/bin/python" ]] || {
    postgres_fail "No usable TibiaHub Python runtime was found."
    return $?
  }

  printf '%s\n' "$TIBIAHUB_BACKEND/venv"
}

postgres_fail() {
  printf '%s\n' "$1" >&2
  return "${2:-2}"
}

load_secure_file() {
  local secret_path="$1"
  local description="$2"
  local mode
  local owner
  local directory_mode
  local directory_owner

  if [[ "$secret_path" != /* || ! -f "$secret_path" || -L "$secret_path" ]]; then
    postgres_fail "$description must be an absolute, regular, non-symlink file: $secret_path"
    return $?
  fi

  mode="$(stat -c '%a' "$secret_path")" || return 1
  owner="$(stat -c '%u' "$secret_path")" || return 1
  directory_mode="$(stat -c '%a' "$(dirname "$secret_path")")" || return 1
  directory_owner="$(stat -c '%u' "$(dirname "$secret_path")")" || return 1

  if [[ "$owner" != "$(id -u)" || $((8#$mode & 077)) -ne 0 ]]; then
    postgres_fail "$description must be owned by the service user and inaccessible to group/other."
    return $?
  fi
  if [[ "$directory_owner" != "$(id -u)" || $((8#$directory_mode & 077)) -ne 0 ]]; then
    postgres_fail "$description directory must be owned by the service user and inaccessible to group/other."
    return $?
  fi

  set -a
  # shellcheck disable=SC1090
  source "$secret_path"
  set +a
  return 0
}

load_tibiahub_environment() {
  if [[ "${_tibiahub_env_loaded:-0}" == "1" ]]; then
    return 0
  fi

  if [[ -z "${DATABASE_URL:-}" ]]; then
    load_secure_file "$TIBIAHUB_RUNTIME_SECRETS_FILE" "TibiaHub runtime secret file" || return $?
  fi
  if [[ -z "${DATABASE_URL:-}" ]]; then
    postgres_fail "DATABASE_URL must be set in the environment or external runtime secret file"
    return $?
  fi

  _tibiahub_env_loaded=1
  _TIBIAHUB_RUNTIME_ENV_LOADED=1
  return 0
}

load_postgres_admin_environment() {
  if [[ "${_tibiahub_admin_env_loaded:-0}" == "1" ]]; then
    return 0
  fi

  load_secure_file "$TIBIAHUB_PROVISION_SECRETS_FILE" "TibiaHub provisioning secret file" || return $?

  if [[ -z "${TIBIAHUB_POSTGRES_ADMIN_MODE:-}" ]]; then
    postgres_fail "TIBIAHUB_POSTGRES_ADMIN_MODE must explicitly select peer or credential_file"
    return $?
  fi
  if [[ -z "${TIBIAHUB_DB_PASSWORD:-}" ]]; then
    postgres_fail "TIBIAHUB_DB_PASSWORD is required in the provisioning secret file"
    return $?
  fi

  case "$TIBIAHUB_POSTGRES_ADMIN_MODE" in
    peer)
      ;;
    credential_file)
      [[ -n "${PGHOST:-}" ]] || { postgres_fail "PGHOST is required in credential_file mode"; return $?; }
      [[ -n "${PGPORT:-}" ]] || { postgres_fail "PGPORT is required in credential_file mode"; return $?; }
      [[ -n "${PGDATABASE:-}" ]] || { postgres_fail "PGDATABASE is required in credential_file mode"; return $?; }
      [[ -n "${PGUSER:-}" ]] || { postgres_fail "PGUSER is required in credential_file mode"; return $?; }
      [[ -n "${PGPASSWORD:-}" ]] || { postgres_fail "PGPASSWORD is required in credential_file mode"; return $?; }
      if [[ "$PGHOST" != "127.0.0.1" && "$PGHOST" != "localhost" && "$PGHOST" != "::1" ]]; then
        postgres_fail "Provisioning administrator connectivity must remain localhost-only."
        return $?
      fi
      if [[ "$PGDATABASE" != "postgres" ]]; then
        postgres_fail "Provisioning administrator maintenance database must be exactly postgres."
        return $?
      fi
      ;;
    *)
      postgres_fail "Unsupported TIBIAHUB_POSTGRES_ADMIN_MODE; use peer or credential_file."
      return $?
      ;;
  esac

  _tibiahub_admin_env_loaded=1
  _TIBIAHUB_ADMIN_ENV_LOADED=1
  return 0
}

postgres_admin_psql() {
  if [[ "${TIBIAHUB_POSTGRES_ADMIN_MODE:-}" == "peer" ]]; then
    sudo -n -u postgres psql -p "${TIBIAHUB_DATABASE_PORT:-5432}" -d postgres "$@"
  else
    psql "$@"
  fi
}

postgres_admin_createdb() {
  if [[ "${TIBIAHUB_POSTGRES_ADMIN_MODE:-}" == "peer" ]]; then
    sudo -n -u postgres createdb -p "${TIBIAHUB_DATABASE_PORT:-5432}" "$@"
  else
    createdb "$@"
  fi
}

postgres_admin_dropdb() {
  if [[ "${TIBIAHUB_POSTGRES_ADMIN_MODE:-}" == "peer" ]]; then
    sudo -n -u postgres dropdb -p "${TIBIAHUB_DATABASE_PORT:-5432}" "$@"
  else
    dropdb "$@"
  fi
}

require_postgres_admin_access() {
  if ! postgres_admin_psql -X -A -t -c 'SELECT 1' >/dev/null; then
    if [[ "${TIBIAHUB_POSTGRES_ADMIN_MODE:-}" == "peer" ]]; then
      postgres_fail "Peer administration was selected, but passwordless sudo access to local postgres is unavailable; no fallback was attempted."
      return $?
    fi
    postgres_fail "Credential-file PostgreSQL administration failed; no peer fallback was attempted."
    return $?
  fi
  return 0
}

database_component() {
  local runtime_dir
  runtime_dir="$(tibiahub_runtime_dir)" || return $?

  APP_ENV="${APP_ENV:-production}" PYTHONPATH="$TIBIAHUB_BACKEND:$TIBIAHUB_ROOT" \
    "$runtime_dir/bin/python" "$TIBIAHUB_ROOT/scripts/postgres-target.py" "$1"
}

postgres_exec() {
  local runtime_dir
  runtime_dir="$(tibiahub_runtime_dir)" || return $?

  PYTHONPATH="$TIBIAHUB_BACKEND:$TIBIAHUB_ROOT" APP_ENV="${APP_ENV:-production}" \
    "$runtime_dir/bin/python" "$TIBIAHUB_ROOT/scripts/postgres-command.py" "$@"
}

require_local_tibiahub_target() {
  local expected_name="${TIBIAHUB_DATABASE_NAME:-tibiahub}"
  local actual_name
  local actual_host

  actual_name="$(database_component name)" || return $?
  actual_host="$(database_component host)" || return $?

  if [[ -z "$expected_name" || "$expected_name" == *"*"* || "$expected_name" == *"?"* ]]; then
    postgres_fail "Refusing blank or wildcard TibiaHub database name."
    return $?
  fi
  if [[ "$actual_name" != "$expected_name" ]]; then
    postgres_fail "Refusing database target: DATABASE_URL name does not match TIBIAHUB_DATABASE_NAME."
    return $?
  fi
  if [[ "$actual_host" != "127.0.0.1" && "$actual_host" != "localhost" && "$actual_host" != "::1" ]]; then
    postgres_fail "Refusing non-local PostgreSQL target."
    return $?
  fi
  if [[ "$(database_component dialect)" != "postgresql" ]]; then
    postgres_fail "Refusing non-PostgreSQL target."
    return $?
  fi
  return 0
}

run_alembic() {
  load_tibiahub_environment || return $?

  local runtime_dir
  runtime_dir="$(tibiahub_runtime_dir)" || return $?

  local alembic_bin="$runtime_dir/bin/alembic"
  local alembic_config="$TIBIAHUB_BACKEND/alembic.ini"
  [[ -x "$alembic_bin" ]] || { postgres_fail "Alembic executable not found: $alembic_bin"; return $?; }
  [[ -f "$alembic_config" ]] || { postgres_fail "Alembic config not found: $alembic_config"; return $?; }

  (
    cd "$TIBIAHUB_BACKEND" || exit 1
    APP_ENV="${APP_ENV:-production}" PYTHONPATH="$TIBIAHUB_BACKEND:$TIBIAHUB_ROOT" \
      "$alembic_bin" -c "$alembic_config" "$@"
  )
}

run_alembic_read_only() {
  case "${1:-}" in
    heads|current|history|check)
      run_alembic "$@"
      ;;
    *)
      postgres_fail "Unsupported read-only Alembic command. Use heads|current|history|check."
      return $?
      ;;
  esac
}
