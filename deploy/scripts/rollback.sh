#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "rollback.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi

set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/lib/ops-common.sh
source "$ROOT/scripts/lib/ops-common.sh"
# shellcheck source=../../scripts/lib/postgres.sh
source "$ROOT/scripts/lib/postgres.sh"

DEPLOY_ROOT="${TIBIAHUB_DEPLOY_ROOT:-/forge/tibiahub-backups/deployments}"
LOCK_FILE="${TIBIAHUB_DEPLOY_LOCK_FILE:-$DEPLOY_ROOT/.deploy.lock}"
RUNTIME_ROOT="${TIBIAHUB_RUNTIME_ROOT:-/forge/tibiahub-runtimes}"
RUNTIME_LINK="$ROOT/backend/runtime-current"
SERVICES=(
  tibiahub-api
  tibiahub-frontend
  tibiahub-raffle-scheduler
  tibiahub-knowledge-worker
  tibiahub-email-worker
  tibiahub-sync-worker
)

if [[ "${1:-}" != "--confirm-rollback-tibiahub" || $# -ne 2 ]]; then
  echo "Usage: deploy/scripts/rollback.sh --confirm-rollback-tibiahub /absolute/deployment/evidence-directory" >&2
  exit 2
fi
requested_evidence="$2"

[[ "$DEPLOY_ROOT" == /* && -d "$DEPLOY_ROOT" && ! -L "$DEPLOY_ROOT" ]] || {
  ops_error "Deployment root must be an absolute, non-symlink directory."
  exit 2
}
deploy_root_mode="$(stat -c '%a' "$DEPLOY_ROOT")"
[[ "$(stat -c '%u' "$DEPLOY_ROOT")" == "$(id -u)" && $((8#$deploy_root_mode & 077)) -eq 0 ]] || {
  ops_error "Deployment root must be owned by the deployment user and private."
  exit 2
}
[[ "$LOCK_FILE" == /* && "$(dirname "$LOCK_FILE")" == "$DEPLOY_ROOT" && ! -L "$LOCK_FILE" ]] || {
  ops_error "Deployment lock must be a non-symlink file inside the deployment root."
  exit 2
}
if [[ "${TIBIAHUB_DEPLOY_LOCK_HELD:-0}" != 1 ]]; then
  exec 9>"$LOCK_FILE"
  chmod 600 "$LOCK_FILE"
  if ! flock -n 9; then
    ops_error "Another TibiaHub deployment or rollback holds the deployment lock."
    exit 2
  fi
fi

[[ "$requested_evidence" == /* && -d "$requested_evidence" && ! -L "$requested_evidence" ]] || {
  ops_error "Rollback requires an absolute, regular evidence directory."
  exit 2
}
evidence_dir="$(realpath -e "$requested_evidence")"
deploy_root_real="$(realpath -e "$DEPLOY_ROOT")"
[[ "$evidence_dir" == "$deploy_root_real"/* && "$(dirname "$evidence_dir")" == "$deploy_root_real" ]] || {
  ops_error "Rollback evidence must be a direct child of the configured deployment root."
  exit 2
}
[[ "$(stat -c '%u' "$evidence_dir")" == "$(id -u)" ]] || {
  ops_error "Rollback evidence must be owned by the deployment user."
  exit 2
}

metadata="$evidence_dir/metadata.env"
snapshot="$evidence_dir/tibiahub.dump"
pm2_state="$evidence_dir/pm2-state.tsv"
restore_list="$evidence_dir/tibiahub.restore.list"
for required_file in "$metadata" "$snapshot" "$evidence_dir/tibiahub.dump.sha256" "$restore_list" "$pm2_state"; do
  [[ -f "$required_file" && ! -L "$required_file" ]] || {
    ops_error "Rollback evidence is incomplete."
    exit 2
  }
done
[[ "$(stat -c '%a' "$snapshot")" == 600 ]] || {
  ops_error "Rollback snapshot permissions are not mode 0600."
  exit 2
}

metadata_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {print $2}' "$metadata"
}

previous_commit="$(metadata_value previous_commit)"
previous_revision="$(metadata_value previous_revision)"
previous_runtime="$(metadata_value previous_runtime)"

if [[ -z "$previous_runtime" ]]; then
  previous_runtime="$ROOT/backend/venv"
fi

[[ "$previous_commit" =~ ^[0-9a-fA-F]{40}$ && "$previous_revision" =~ ^[A-Za-z0-9_]+$ ]] || {
  ops_error "Rollback metadata is invalid."
  exit 2
}

cd "$ROOT"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
  ops_error "Rollback requires a clean working tree."
  exit 2
}
git cat-file -e "$previous_commit^{commit}"

CURRENT_STEP_NAME=""
CURRENT_STEP_COMMAND=""

on_rollback_error() {
  local exit_code=$?
  local failed_line="${BASH_LINENO[0]:-unknown}"
  local failed_function="${FUNCNAME[1]:-main}"
  local failed_command="${CURRENT_STEP_COMMAND:-${BASH_COMMAND:-unknown}}"
  local stdout_log="${OPS_LAST_STEP_STDOUT:-unknown}"
  local stderr_log="${OPS_LAST_STEP_STDERR:-unknown}"
  ops_write_failure_record "$evidence_dir/ROLLBACK_FAILED_INFO" "$exit_code" "${CURRENT_STEP_NAME:-unknown}" "$failed_line" "$failed_function" "$failed_command" "$stdout_log" "$stderr_log"
  chmod 600 "$evidence_dir/ROLLBACK_FAILED_INFO"
  exit "$exit_code"
}
trap on_rollback_error ERR

run_step() {
  local step_name="$1"
  shift
  CURRENT_STEP_NAME="$step_name"
  CURRENT_STEP_COMMAND="$(ops_safe_command_name "$@")"
  ops_info "Rollback step $step_name"
  ops_run_deploy_step "$evidence_dir" "$step_name" "$@"
}

load_runtime_and_target() {
  load_tibiahub_environment
  TIBIAHUB_DATABASE_NAME=tibiahub require_local_tibiahub_target
}

validate_snapshot() {
  (cd "$evidence_dir" && sha256sum --check --status tibiahub.dump.sha256)
  pg_restore --list "$snapshot" >/dev/null
}

stop_services() {
  local service
  for service in "${SERVICES[@]}"; do
    if pm2 describe "$service" >/dev/null 2>&1; then
      pm2 stop "$service"
    fi
  done
}

restore_runtime() {
  local temporary_link="$ROOT/backend/.runtime-current.rollback.$$"

  case "$previous_runtime" in
    "$ROOT/backend/venv"|"$RUNTIME_ROOT"/*)
      ;;
    *)
      echo "Rollback runtime is outside an allowed path." >&2
      return 1
      ;;
  esac

  [[ -x "$previous_runtime/bin/python" ]] || {
    echo "Rollback runtime is unavailable." >&2
    return 1
  }

  if [[ -e "$RUNTIME_LINK" && ! -L "$RUNTIME_LINK" ]]; then
    echo "Refusing to replace non-symlink runtime-current." >&2
    return 1
  fi

  rm -f -- "$temporary_link"
  ln -s "$previous_runtime" "$temporary_link"
  mv -Tf "$temporary_link" "$RUNTIME_LINK"

  export TIBIAHUB_PYTHON_RUNTIME="$previous_runtime"
}


restore_database() {
  local database_name
  database_name="$(database_component name)"
  [[ "$database_name" == tibiahub ]] || {
    echo "Rollback refused an unexpected database." >&2
    return 1
  }
  postgres_exec pg_restore --dbname="$database_name" --clean --if-exists --single-transaction --exit-on-error --no-owner --no-acl --use-list="$restore_list" "$snapshot"
}

verify_revision() {
  restored_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
  restored_revision="${restored_revision//$'\n'/}"
  [[ "$restored_revision" == "$previous_revision" ]]
}

restore_frontend() {
  [[ -d "$evidence_dir/frontend-dist-previous" ]] || {
    echo "The previous-commit frontend rollback build is missing." >&2
    return 1
  }
  if [[ -e "$ROOT/frontend/dist" && ! -d "$ROOT/frontend/dist" ]]; then
    echo "Refusing to replace a non-directory frontend dist path." >&2
    return 1
  fi
  rm -rf -- "$ROOT/frontend/dist"
  cp -a "$evidence_dir/frontend-dist-previous" "$ROOT/frontend/dist"
}

pm2_start_service() {
  local service="$1"

  # PM2 reloads an existing process using its previously registered
  # executable path. Recreate the bounded TibiaHub service so changes
  # such as venv/bin/python -> runtime-current/bin/python take effect.
  if pm2 describe "$service" >/dev/null 2>&1; then
    pm2 delete "$service"
  fi

  env -i HOME="$HOME" USER="${USER:-}" PATH="$PATH" PM2_HOME="${PM2_HOME:-$HOME/.pm2}" \
    pm2 start "$ROOT/ecosystem.config.js" --only "$service"
}

pm2_service_online() {
  local service="$1"
  pm2 jlist | jq -e --arg name "$service" 'any(.[]; .name == $name and .pm2_env.status == "online" and ((.pid // 0) > 0))' >/dev/null
}

wait_for_pm2_online() {
  local service="$1"
  local attempt
  for attempt in $(seq 1 30); do
    if pm2_service_online "$service"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

restore_pm2_states() {
  declare -A previous_status=()
  while IFS=$'\t' read -r service status; do
    previous_status["$service"]="$status"
  done <"$pm2_state"

  local service
  for service in "${SERVICES[@]}"; do
    case "${previous_status[$service]:-absent}" in
      online)
        local pm2_status=0
        if ! pm2_start_service "$service"; then
          pm2_status=$?
          ops_warn "PM2 returned non-zero for $service during rollback; validating online state."
        fi
        if ! wait_for_pm2_online "$service"; then
          if [[ "$pm2_status" -ne 0 ]]; then
            return "$pm2_status"
          fi
          return 1
        fi
        ;;
      absent)
        if pm2 describe "$service" >/dev/null 2>&1; then
          pm2 delete "$service"
        fi
        ;;
      *)
        if pm2 describe "$service" >/dev/null 2>&1; then
          pm2 stop "$service"
        fi
        ;;
    esac
  done
}

write_state() {
  rollback_at="$(ops_now_utc)"
  printf 'rolled_back_at=%s\nrestored_commit=%s\nrestored_revision=%s\n' "$rollback_at" "$previous_commit" "$restored_revision" >"$evidence_dir/rollback.env"
  chmod 600 "$evidence_dir/rollback.env"

  state_tmp="$DEPLOY_ROOT/.current.env.$$"
  {
    printf 'deployed_commit=%s\n' "$previous_commit"
    printf 'alembic_revision=%s\n' "$previous_revision"
    printf 'snapshot_dir=%s\n' "$evidence_dir"
    printf 'runtime_target=%s\n' "$previous_runtime"
    printf 'deployed_at=%s\n' "$rollback_at"
  } >"$state_tmp"
  chmod 600 "$state_tmp"
  mv "$state_tmp" "$DEPLOY_ROOT/current.env"
}

run_step "010-validate-snapshot" validate_snapshot
run_step "020-load-runtime-target" load_runtime_and_target
run_step "030-stop-services" stop_services
run_step "040-checkout-previous-commit" git switch --detach "$previous_commit"
run_step "045-restore-backend-runtime" restore_runtime
run_step "050-restore-database" restore_database
run_step "060-verify-revision" verify_revision
run_step "070-restore-frontend" restore_frontend
run_step "080-restore-pm2-state" restore_pm2_states
run_step "090-write-state" write_state

trap - ERR

echo "Rollback restored commit $previous_commit and Alembic revision $restored_revision."
echo "Rollback evidence remains at $evidence_dir"
echo "Repository is detached at $previous_commit. To return to the deployment branch, run:"
echo "  git switch develop"
echo "  git pull --ff-only origin develop"
