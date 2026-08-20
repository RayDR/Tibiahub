#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "deploy.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi

set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/lib/ops-common.sh
source "$ROOT/scripts/lib/ops-common.sh"
# shellcheck source=../../scripts/lib/postgres.sh
source "$ROOT/scripts/lib/postgres.sh"

EXPECTED_REVISION=""
DEPLOY_ROOT="${TIBIAHUB_DEPLOY_ROOT:-/forge/tibiahub-backups/deployments}"
LOCK_FILE="${TIBIAHUB_DEPLOY_LOCK_FILE:-$DEPLOY_ROOT/.deploy.lock}"
RUNTIME_ROOT="${TIBIAHUB_RUNTIME_ROOT:-/forge/tibiahub-runtimes}"
RUNTIME_LINK="$ROOT/backend/runtime-current"
FRONTEND_DIR="$ROOT/frontend"
FRONTEND_DEPS_STAMP="$FRONTEND_DIR/node_modules/.tibiahub-dependency-inputs.sha256"
candidate_runtime=""
previous_runtime=""
runtime_is_ephemeral=0
SERVICES=(
  tibiahub-api
  tibiahub-frontend
  tibiahub-raffle-scheduler
  tibiahub-knowledge-worker
  tibiahub-email-worker
  tibiahub-sync-worker
)
LOCAL_URLS=(
  http://127.0.0.1:8001/api/v1/health
  http://127.0.0.1:8001/api/v1/ready
  http://127.0.0.1:5174/
)
PUBLIC_URLS=(
  https://tibiahub.domoforge.com/api/v1/health
  https://tibiahub.domoforge.com/api/v1/ready
  https://tibiahub.domoforge.com/
)

usage() {
  cat >&2 <<'USAGE'
Usage: deploy/scripts/deploy.sh --confirm-deploy-tibiahub [--previous-commit COMMIT]
       deploy/scripts/deploy.sh --dry-run [--previous-commit COMMIT]
USAGE
  exit 2
}

confirm=0
dry_run=0
provided_previous_commit=""
while (($#)); do
  case "$1" in
    --confirm-deploy-tibiahub)
      confirm=1
      shift
      ;;
    --previous-commit)
      [[ $# -ge 2 ]] || usage
      provided_previous_commit="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    *)
      usage
      ;;
  esac
done
if [[ "$dry_run" -ne 1 && "$confirm" -ne 1 ]]; then
  usage
fi

ops_require_commands flock git pg_dump pg_restore sha256sum jq curl pm2 npm node bash awk sed find stat realpath python3 || exit $?

[[ "$DEPLOY_ROOT" == /* && ! -L "$DEPLOY_ROOT" ]] || {
  ops_error "Deployment root must be an absolute, non-symlink directory."
  exit 2
}
mkdir -p "$DEPLOY_ROOT"
chmod 700 "$DEPLOY_ROOT"
deploy_root_mode="$(stat -c '%a' "$DEPLOY_ROOT")"
[[ "$(stat -c '%u' "$DEPLOY_ROOT")" == "$(id -u)" && $((8#$deploy_root_mode & 077)) -eq 0 ]] || {
  ops_error "Deployment root must be owned by the deployment user and private."
  exit 2
}
[[ "$LOCK_FILE" == /* && "$(dirname "$LOCK_FILE")" == "$DEPLOY_ROOT" && ! -L "$LOCK_FILE" ]] || {
  ops_error "Deployment lock must be a non-symlink file inside the deployment root."
  exit 2
}
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
if ! flock -n 9; then
  ops_error "Another TibiaHub deployment or rollback holds the deployment lock."
  exit 2
fi

cd "$ROOT"

CURRENT_STEP_NAME=""
CURRENT_STEP_COMMAND=""
OPS_LAST_STEP_STDOUT=""
OPS_LAST_STEP_STDERR=""
rollback_armed=0

on_error() {
  local exit_code=$?
  local failed_line="${BASH_LINENO[0]:-unknown}"
  local failed_function="${FUNCNAME[1]:-main}"
  local failed_command="${CURRENT_STEP_COMMAND:-${BASH_COMMAND:-unknown}}"
  local stdout_log="${OPS_LAST_STEP_STDOUT:-unknown}"
  local stderr_log="${OPS_LAST_STEP_STDERR:-unknown}"

  trap - ERR

  if [[ -n "${evidence_dir:-}" ]]; then
    ops_write_failure_record \
      "$evidence_dir/FAILED" \
      "$exit_code" \
      "${CURRENT_STEP_NAME:-unknown}" \
      "$failed_line" \
      "$failed_function" \
      "$failed_command" \
      "$stdout_log" \
      "$stderr_log"
    chmod 600 "$evidence_dir/FAILED"
  fi

  if [[ "$rollback_armed" == 1 ]]; then
    if TIBIAHUB_DEPLOY_LOCK_HELD=1 "$ROOT/deploy/scripts/rollback.sh" --confirm-rollback-tibiahub "$evidence_dir"; then
      touch "$evidence_dir/ROLLBACK_SUCCEEDED"
    else
      touch "$evidence_dir/ROLLBACK_FAILED"
    fi
  fi

  ops_error "Deployment failed; evidence preserved at ${evidence_dir:-$DEPLOY_ROOT}"
  exit "$exit_code"
}
trap on_error ERR

run_step() {
  local step_name="$1"
  shift
  CURRENT_STEP_NAME="$step_name"
  CURRENT_STEP_COMMAND="$(ops_safe_command_name "$@")"
  ops_info "Running step $step_name"
  ops_run_deploy_step "$evidence_dir" "$step_name" "$@"
}

sanitize_step_suffix() {
  printf '%s' "$1" | sed -E 's#[^A-Za-z0-9._-]#_#g'
}

preflight_git_state() {
  if [[ "$dry_run" == 1 ]]; then
    target_commit="$(git rev-parse HEAD)"
    remote_commit="$target_commit"
    return 0
  fi
  [[ "$(git branch --show-current)" == "develop" ]] || {
    echo "Deployment requires the local develop branch." >&2
    return 1
  }
  [[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Deployment requires a completely clean working tree." >&2
    return 1
  }
  git fetch --quiet origin develop
  target_commit="$(git rev-parse HEAD)"
  remote_commit="$(git rev-parse refs/remotes/origin/develop)"
  [[ "$target_commit" == "$remote_commit" ]] || {
    echo "Deployment requires local develop to equal origin/develop exactly." >&2
    return 1
  }
}

prepare_candidate_runtime() {
  local requirements_sha
  local recorded_sha=""

  requirements_sha="$(
    sha256sum "$ROOT/backend/requirements.txt" |
      awk '{print $1}'
  )"

  if [[ "$dry_run" == 1 ]]; then
    candidate_runtime="$(
      mktemp -d /tmp/tibiahub-runtime-dryrun-XXXXXX
    )"
    runtime_is_ephemeral=1
  else
    [[ "$RUNTIME_ROOT" == /* && ! -L "$RUNTIME_ROOT" ]] || {
      echo "Runtime root must be an absolute, non-symlink directory." >&2
      return 1
    }

    mkdir -p "$RUNTIME_ROOT"
    chmod 700 "$RUNTIME_ROOT"

    candidate_runtime="$RUNTIME_ROOT/$target_commit"

    if [[ -f "$candidate_runtime/.requirements.sha256" ]]; then
      recorded_sha="$(
        cat "$candidate_runtime/.requirements.sha256"
      )"
    fi

    if [[
      "$recorded_sha" == "$requirements_sha"
      && -x "$candidate_runtime/bin/python"
      && -x "$candidate_runtime/bin/alembic"
    ]]; then
      export TIBIAHUB_PYTHON_RUNTIME="$candidate_runtime"
      return 0
    fi

    rm -rf -- "$candidate_runtime"
  fi

  python3 -m venv "$candidate_runtime"

  "$candidate_runtime/bin/python" -m pip install \
    --disable-pip-version-check \
    --no-input \
    --requirement "$ROOT/backend/requirements.txt"

  "$candidate_runtime/bin/python" -m pip check

  "$candidate_runtime/bin/python" - <<'PY_RUNTIME'
import alembic
import fastapi
import httpx
import jwt
import pydantic
import pydantic_settings
import sqlalchemy
import uvicorn
PY_RUNTIME

  printf '%s\n' "$requirements_sha" \
    >"$candidate_runtime/.requirements.sha256"

  export TIBIAHUB_PYTHON_RUNTIME="$candidate_runtime"
}


capture_previous_runtime() {
  if [[ -L "$RUNTIME_LINK" ]]; then
    previous_runtime="$(realpath -e "$RUNTIME_LINK")"
  elif [[ -e "$RUNTIME_LINK" ]]; then
    echo "Backend runtime-current must be a symlink." >&2
    return 1
  else
    previous_runtime="$ROOT/backend/venv"
  fi

  case "$previous_runtime" in
    "$ROOT/backend/venv"|"$RUNTIME_ROOT"/*)
      ;;
    *)
      echo "Previous backend runtime is outside an allowed path." >&2
      return 1
      ;;
  esac

  [[ -x "$previous_runtime/bin/python" ]] || {
    echo "Previous backend runtime is unavailable." >&2
    return 1
  }
}


activate_candidate_runtime() {
  local temporary_link="$ROOT/backend/.runtime-current.$$"

  [[ "$candidate_runtime" == "$RUNTIME_ROOT"/* ]] || {
    echo "Candidate runtime is outside the runtime root." >&2
    return 1
  }

  [[ -x "$candidate_runtime/bin/python" ]] || {
    echo "Candidate backend runtime is incomplete." >&2
    return 1
  }

  if [[ -e "$RUNTIME_LINK" && ! -L "$RUNTIME_LINK" ]]; then
    echo "Refusing to replace non-symlink runtime-current." >&2
    return 1
  fi

  rm -f -- "$temporary_link"
  ln -s "$candidate_runtime" "$temporary_link"
  mv -Tf "$temporary_link" "$RUNTIME_LINK"

  export TIBIAHUB_PYTHON_RUNTIME="$candidate_runtime"
}


preflight_alembic_head() {
  mapfile -t migration_heads < <(
    APP_ENV=test DATABASE_URL="sqlite+pysqlite:///:memory:" PYTHONPATH="$ROOT/backend:$ROOT" \
      "$candidate_runtime/bin/alembic" -c "$ROOT/backend/alembic.ini" heads | awk '{print $1}'
  )

  if [[ ${#migration_heads[@]} -ne 1 ]]; then
    echo "Deployment requires exactly one Alembic HEAD; found ${#migration_heads[@]}." >&2
    if [[ ${#migration_heads[@]} -gt 0 ]]; then
      printf 'Alembic HEAD: %s\n' "${migration_heads[@]}" >&2
    fi
    return 1
  fi

  EXPECTED_REVISION="${migration_heads[0]}"
  [[ "$EXPECTED_REVISION" =~ ^[A-Za-z0-9_]+$ ]] || {
    echo "Resolved Alembic HEAD has an invalid revision identifier." >&2
    return 1
  }

  echo "Resolved Alembic target revision: $EXPECTED_REVISION"
}

preflight_runtime_env() {
  load_secure_file "$TIBIAHUB_RUNTIME_SECRETS_FILE" "TibiaHub runtime secret file"
  load_tibiahub_environment
}

preflight_db_target() {
  TIBIAHUB_DATABASE_NAME=tibiahub require_local_tibiahub_target
}

preflight_production_revision_readable() {
  production_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
  production_revision="${production_revision//$'\n'/}"
  [[ "$production_revision" =~ ^[A-Za-z0-9_]+$ ]]
}


preflight_alembic_upgrade_path() {
  if [[ "$production_revision" == "$EXPECTED_REVISION" ]]; then
    # If production is already at HEAD, Alembic check is valid here.
    run_alembic_read_only check
    return 0
  fi

  (
    cd "$ROOT/backend"

    PYTHONPATH="$ROOT/backend:$ROOT" \
      "$candidate_runtime/bin/python" - \
      "$ROOT/backend/alembic.ini" \
      "$production_revision" \
      "$EXPECTED_REVISION" <<'PY_ALEMBIC_PATH'
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

config_path, current_revision, expected_revision = sys.argv[1:4]

try:
    config = Config(config_path)
    script = ScriptDirectory.from_config(config)

    current = script.get_revision(current_revision)
    expected = script.get_revision(expected_revision)

    if current is None:
        raise RuntimeError(
            f"Production Alembic revision does not exist in this release: "
            f"{current_revision}"
        )

    if expected is None:
        raise RuntimeError(
            f"Expected Alembic revision does not exist in this release: "
            f"{expected_revision}"
        )

    if script.get_current_head() != expected_revision:
        raise RuntimeError(
            f"Expected revision {expected_revision} is not the single "
            f"Alembic HEAD."
        )

    revisions = list(
        script.iterate_revisions(
            expected_revision,
            current_revision,
        )
    )

    if not revisions:
        raise RuntimeError(
            f"No upgrade path exists from {current_revision} "
            f"to {expected_revision}."
        )

    path = [current_revision] + [
        revision.revision
        for revision in reversed(revisions)
    ]

    print(
        "Validated Alembic upgrade path: "
        + " -> ".join(path)
    )

except Exception as exc:
    print(
        f"Unsafe Alembic upgrade path: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY_ALEMBIC_PATH
  )
}

preflight_backend_imports() {
  PYTHONPATH="$ROOT/backend:$ROOT" APP_ENV="${APP_ENV:-production}" "$candidate_runtime/bin/python" -c "import app.core.config"
}

preflight_fastapi_import() {
  PYTHONPATH="$ROOT/backend:$ROOT" APP_ENV="${APP_ENV:-production}" "$candidate_runtime/bin/python" -c "import main"
}

preflight_worker_imports() {
  PYTHONPATH="$ROOT/backend:$ROOT" APP_ENV="${APP_ENV:-production}" \
    "$candidate_runtime/bin/python" -c "import app.workers.sync_worker, app.workers.email_worker, app.workers.raffle_scheduler, app.knowledge.workers.knowledge_worker"
}

frontend_dependency_fingerprint() {
  [[ -f "$FRONTEND_DIR/package.json" && -f "$FRONTEND_DIR/package-lock.json" ]] || {
    echo "Frontend package.json and package-lock.json are required." >&2
    return 1
  }

  (
    cd "$FRONTEND_DIR"
    sha256sum package.json package-lock.json | sha256sum | awk '{print $1}'
  )
}

prepare_frontend_dependencies() {
  local expected_sha
  local recorded_sha=""

  expected_sha="$(frontend_dependency_fingerprint)" || return 1

  if [[ -L "$FRONTEND_DIR/node_modules" ]]; then
    echo "Refusing to mutate symlinked frontend/node_modules; remove the symlink so deploy can prepare isolated dependencies." >&2
    return 1
  fi

  if [[ -f "$FRONTEND_DEPS_STAMP" ]]; then
    recorded_sha="$(cat "$FRONTEND_DEPS_STAMP")"
  fi

  if [[
    "$recorded_sha" == "$expected_sha"
    && -x "$FRONTEND_DIR/node_modules/.bin/vite"
  ]]; then
    echo "Frontend dependencies already match package inputs."
    return 0
  fi

  echo "Preparing frontend dependencies with npm ci."
  (
    cd "$FRONTEND_DIR"
    npm ci --prefer-offline --no-audit --no-fund
  )

  [[ -x "$FRONTEND_DIR/node_modules/.bin/vite" ]] || {
    echo "Frontend dependency installation did not provide Vite." >&2
    return 1
  }

  printf '%s\n' "$expected_sha" >"$FRONTEND_DEPS_STAMP"
  echo "Frontend dependencies prepared for package inputs: $expected_sha"
}

preflight_frontend_build() {
  (cd "$FRONTEND_DIR" && npm run build -- --outDir "$staged_dist")
  [[ -f "$staged_dist/index.html" ]]
}

preflight_pm2_config() {
  node -e 'const fs=require("fs");const p=process.argv[1];const c=fs.readFileSync(p,"utf8");if(!c.includes("module.exports")){process.exit(1)}' "$ROOT/ecosystem.config.js"
}

capture_pm2_state() {
  local allowed_services_json
  allowed_services_json="$(printf '%s\n' "${SERVICES[@]}" | jq -R . | jq -s .)"
  pm2 jlist | jq --argjson allowed "$allowed_services_json" '
    . as $processes |
    [$allowed[] as $name |
      ([$processes[] | select(.name == $name)][0]) as $process |
      {
        name: $name,
        status: ($process.pm2_env.status // "absent"),
        pid: ($process.pid // null),
        restart_time: ($process.pm2_env.restart_time // null),
        started_at: ($process.pm2_env.pm_uptime // null),
        cwd: ($process.pm2_env.pm_cwd // null),
        script: ($process.pm2_env.pm_exec_path // null)
      }
    ]' >"$evidence_dir/pm2-state.json"
  jq -r '.[] | [.name, .status] | @tsv' "$evidence_dir/pm2-state.json" >"$evidence_dir/pm2-state.tsv"
  chmod 600 "$evidence_dir/pm2-state.json" "$evidence_dir/pm2-state.tsv"
}

build_previous_frontend() {
  previous_worktree="$evidence_dir/previous-worktree"
  git worktree add --quiet --detach "$previous_worktree" "$previous_commit"
  (
    cd "$previous_worktree/frontend"
    npm ci --prefer-offline --no-audit --no-fund
    npm run build -- --outDir "$evidence_dir/frontend-dist-previous"
  )
  [[ -f "$evidence_dir/frontend-dist-previous/index.html" ]]
  git worktree remove --force "$previous_worktree"
}

stop_services() {
  local service
  for service in "${SERVICES[@]}"; do
    if pm2 describe "$service" >/dev/null 2>&1; then
      pm2 stop "$service"
    fi
  done
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

start_service_checked() {
  local service="$1"
  local pm2_status=0
  if ! pm2_start_service "$service"; then
    pm2_status=$?
    ops_warn "PM2 returned non-zero for $service; validating online state before deciding failure."
  fi
  if wait_for_pm2_online "$service"; then
    return 0
  fi
  if [[ "$pm2_status" -ne 0 ]]; then
    return "$pm2_status"
  fi
  return 1
}

wait_for_url() {
  local url="$1"
  local attempt
  for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "Health check failed: $url" >&2
  return 1
}

verify_worker_heartbeats() {
  worker_heartbeat_count="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 <<'SQL'
SELECT
  (SELECT EXISTS (SELECT 1 FROM raffle_scheduler_state WHERE heartbeat_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM knowledge_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM email_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM sync_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int;
SQL
)"
  worker_heartbeat_count="${worker_heartbeat_count//$'\n'/}"
  [[ "$worker_heartbeat_count" == 4 ]]
}

preflight_git_state

if [[ "$dry_run" == 1 ]]; then
  evidence_dir="$(mktemp -d /tmp/tibiahub-deploy-dryrun-XXXXXX)"
else
  evidence_dir="$DEPLOY_ROOT/$(ops_now_utc)-${target_commit:0:12}"
  mkdir "$evidence_dir"
  chmod 700 "$evidence_dir"
fi
metadata="$evidence_dir/metadata.env"
staged_dist="$evidence_dir/frontend-dist-new"

run_step "010-preflight-git-state" preflight_git_state
run_step "015-preflight-backend-runtime" prepare_candidate_runtime
run_step "020-preflight-alembic-head" preflight_alembic_head
run_step "030-preflight-runtime-env" preflight_runtime_env
run_step "040-preflight-db-target" preflight_db_target
run_step "050-preflight-production-revision" preflight_production_revision_readable
run_step "060-preflight-backend-import" preflight_backend_imports
run_step "070-preflight-fastapi-import" preflight_fastapi_import
run_step "080-preflight-worker-imports" preflight_worker_imports
run_step "085-preflight-frontend-dependencies" prepare_frontend_dependencies
run_step "090-preflight-frontend-build" preflight_frontend_build
run_step "100-preflight-pm2-config" preflight_pm2_config
run_step "110-preflight-alembic-heads" run_alembic_read_only heads
run_step "120-preflight-alembic-current" run_alembic_read_only current
run_step "130-preflight-alembic-history" run_alembic_read_only history
run_step "140-preflight-alembic-upgrade-path" preflight_alembic_upgrade_path

if [[ "$dry_run" == 1 ]]; then
  touch "$evidence_dir/DRY_RUN_SUCCEEDED"
  ops_info "Dry-run preflight succeeded. Evidence: $evidence_dir"

  if [[ "$runtime_is_ephemeral" == 1 ]]; then
    rm -rf -- "$candidate_runtime"
  fi

  trap - ERR
  exit 0
fi

state_file="$DEPLOY_ROOT/current.env"
state_previous_commit=""
if [[ -f "$state_file" ]]; then
  [[ ! -L "$state_file" ]] || {
    ops_error "Deployment state file must not be a symlink."
    exit 2
  }
  state_previous_commit="$(awk -F= '$1 == "deployed_commit" {print $2}' "$state_file")"
fi

previous_commit_source="recorded"
if [[ -n "$provided_previous_commit" ]]; then
  previous_commit="$provided_previous_commit"
  previous_commit_source="explicit"
  if [[ -n "$state_previous_commit" && "$provided_previous_commit" != "$state_previous_commit" ]]; then
    ops_warn "Recorded deployed commit $state_previous_commit differs from explicitly provided previous commit $provided_previous_commit; using the explicit value."
  fi
else
  previous_commit="$state_previous_commit"
fi

[[ "$previous_commit" =~ ^[0-9a-fA-F]{40}$ ]] || {
  ops_error "No valid recorded deployment commit exists; pass --previous-commit with the deployed 40-character commit."
  exit 2
}
git cat-file -e "$previous_commit^{commit}"

capture_previous_runtime

previous_revision="$production_revision"
[[ "$previous_revision" =~ ^[A-Za-z0-9_]+$ ]] || {
  ops_error "Unable to establish the current production Alembic revision safely."
  exit 2
}

{
  printf 'target_commit=%s\n' "$target_commit"
  printf 'previous_commit=%s\n' "$previous_commit"
  printf 'previous_commit_source=%s\n' "$previous_commit_source"
  printf 'recorded_previous_commit=%s\n' "$state_previous_commit"
  printf 'target_revision=%s\n' "$EXPECTED_REVISION"
  printf 'previous_revision=%s\n' "$previous_revision"
  printf 'target_runtime=%s\n' "$candidate_runtime"
  printf 'previous_runtime=%s\n' "$previous_runtime"
  printf 'started_at=%s\n' "$(ops_now_utc)"
} >"$metadata"
chmod 600 "$metadata"

snapshot="$evidence_dir/tibiahub.dump"
run_step "150-backup-snapshot" postgres_exec pg_dump --format=custom --no-owner --no-acl --file="$snapshot"
chmod 600 "$snapshot"
run_step "160-backup-validate" pg_restore --list "$snapshot"
pg_restore --list "$snapshot" >"$evidence_dir/tibiahub.dump.list"
chmod 600 "$evidence_dir/tibiahub.dump.list"
awk '!/ EXTENSION / && !/ TABLE DATA public spatial_ref_sys /' "$evidence_dir/tibiahub.dump.list" >"$evidence_dir/tibiahub.restore.list"
chmod 600 "$evidence_dir/tibiahub.restore.list"
[[ -s "$evidence_dir/tibiahub.restore.list" ]] || {
  ops_error "The extension-preserving restore catalog is empty."
  exit 1
}
sha256sum "$snapshot" >"$evidence_dir/tibiahub.dump.sha256"
chmod 600 "$evidence_dir/tibiahub.dump.sha256"

if [[ -d "$ROOT/frontend/dist" ]]; then
  run_step "170-stage-current-frontend" cp -a "$ROOT/frontend/dist" "$evidence_dir/frontend-dist-current"
  touch "$evidence_dir/frontend-dist-current.present"
else
  touch "$evidence_dir/frontend-dist-current.absent"
fi

run_step "180-capture-pm2-state" capture_pm2_state
run_step "190-build-rollback-frontend" build_previous_frontend

rollback_armed=1
run_step "200-stop-services" stop_services
run_step "205-activate-backend-runtime" activate_candidate_runtime
run_step "210-alembic-upgrade" run_alembic upgrade head

resulting_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
resulting_revision="${resulting_revision//$'\n'/}"
[[ "$resulting_revision" == "$EXPECTED_REVISION" ]] || {
  ops_error "Production did not reach the expected Alembic revision."
  false
}

run_step "215-post-migrate-alembic-check" run_alembic_read_only check

if [[ -e "$ROOT/frontend/dist" && ! -d "$ROOT/frontend/dist" ]]; then
  ops_error "Refusing to replace a non-directory frontend dist path."
  false
fi
run_step "220-install-frontend" bash -c 'rm -rf -- "$1" && mv "$2" "$1" && [[ -f "$1/index.html" ]]' bash "$ROOT/frontend/dist" "$staged_dist"

for service in "${SERVICES[@]}"; do
  run_step "230-start-${service}" start_service_checked "$service"
done

for url in "${LOCAL_URLS[@]}"; do
  run_step "240-health-local-$(sanitize_step_suffix "$url")" wait_for_url "$url"
done
for url in "${PUBLIC_URLS[@]}"; do
  run_step "250-health-public-$(sanitize_step_suffix "$url")" wait_for_url "$url"
done

run_step "260-worker-heartbeats" verify_worker_heartbeats

completed_at="$(ops_now_utc)"
state_tmp="$DEPLOY_ROOT/.current.env.$$"
{
  printf 'deployed_commit=%s\n' "$target_commit"
  printf 'alembic_revision=%s\n' "$EXPECTED_REVISION"
  printf 'snapshot_dir=%s\n' "$evidence_dir"
  printf 'runtime_target=%s\n' "$candidate_runtime"
  printf 'deployed_at=%s\n' "$completed_at"
} >"$state_tmp"
chmod 600 "$state_tmp"
mv "$state_tmp" "$state_file"
printf 'completed_at=%s\n' "$completed_at" >>"$metadata"
touch "$evidence_dir/SUCCEEDED"

trap - ERR
snapshot_sha256="$(awk '{print $1}' "$evidence_dir/tibiahub.dump.sha256")"

echo "Deployment succeeded."
echo "Target commit: $target_commit"
echo "Previous commit: $previous_commit"
echo "Previous Alembic revision: $previous_revision"
echo "Resulting Alembic revision: $resulting_revision"
echo "Snapshot directory: $evidence_dir"
echo "Snapshot SHA-256: $snapshot_sha256"
