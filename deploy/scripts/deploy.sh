#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/postgres-common.sh
source "$ROOT/scripts/postgres-common.sh"

EXPECTED_REVISION="maintenance_sync_20260804"
DEPLOY_ROOT="${TIBIAHUB_DEPLOY_ROOT:-/forge/tibiahub-backups/deployments}"
LOCK_FILE="${TIBIAHUB_DEPLOY_LOCK_FILE:-$DEPLOY_ROOT/.deploy.lock}"
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
  echo "Usage: $0 --confirm-deploy-tibiahub [--previous-commit COMMIT]" >&2
  exit 2
}

confirm=""
provided_previous_commit=""
while (($#)); do
  case "$1" in
    --confirm-deploy-tibiahub)
      [[ -z "$confirm" ]] || usage
      confirm=1
      shift
      ;;
    --previous-commit)
      [[ $# -ge 2 && -z "$provided_previous_commit" ]] || usage
      provided_previous_commit="$2"
      shift 2
      ;;
    *) usage ;;
  esac
done
[[ "$confirm" == 1 ]] || usage

for command_name in flock git pg_dump pg_restore sha256sum jq curl pm2 npm; do
  command -v "$command_name" >/dev/null || {
    echo "Required deployment command is unavailable: $command_name" >&2
    exit 2
  }
done

[[ "$DEPLOY_ROOT" == /* && ! -L "$DEPLOY_ROOT" ]] || {
  echo "Deployment root must be an absolute, non-symlink directory." >&2
  exit 2
}
mkdir -p "$DEPLOY_ROOT"
chmod 700 "$DEPLOY_ROOT"
deploy_root_mode="$(stat -c '%a' "$DEPLOY_ROOT")"
[[ "$(stat -c '%u' "$DEPLOY_ROOT")" == "$(id -u)" && $((8#$deploy_root_mode & 077)) -eq 0 ]] || {
  echo "Deployment root must be owned by the deployment user and private." >&2
  exit 2
}
[[ "$LOCK_FILE" == /* && "$(dirname "$LOCK_FILE")" == "$DEPLOY_ROOT" && ! -L "$LOCK_FILE" ]] || {
  echo "Deployment lock must be a non-symlink file inside the deployment root." >&2
  exit 2
}
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
if ! flock -n 9; then
  echo "Another TibiaHub deployment or rollback holds the deployment lock." >&2
  exit 2
fi

cd "$ROOT"
[[ "$(git branch --show-current)" == "develop" ]] || {
  echo "Deployment requires the local develop branch." >&2
  exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
  echo "Deployment requires a completely clean working tree." >&2
  exit 2
}
git fetch --quiet origin develop
target_commit="$(git rev-parse HEAD)"
remote_commit="$(git rev-parse refs/remotes/origin/develop)"
[[ "$target_commit" == "$remote_commit" ]] || {
  echo "Deployment requires local develop to equal origin/develop exactly." >&2
  exit 2
}

mapfile -t migration_heads < <(
  APP_ENV=test DATABASE_URL="sqlite+pysqlite:///:memory:" PYTHONPATH="$ROOT/backend:$ROOT" \
    "$ROOT/backend/venv/bin/alembic" -c "$ROOT/backend/alembic.ini" heads | awk '{print $1}'
)
[[ ${#migration_heads[@]} -eq 1 && "${migration_heads[0]}" == "$EXPECTED_REVISION" ]] || {
  echo "Deployment refused: the repository does not have the expected single Alembic head." >&2
  exit 2
}

load_tibiahub_environment
TIBIAHUB_DATABASE_NAME=tibiahub require_local_tibiahub_target
restore_ownership_violations="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 <<'SQL'
SELECT count(*) FROM (
  SELECT c.oid
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
    AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)
    AND NOT EXISTS (
      SELECT 1 FROM pg_depend d
      JOIN pg_extension e ON e.oid = d.refobjid
      WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
    )
  UNION ALL
  SELECT p.oid
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public'
    AND p.proowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)
    AND NOT EXISTS (
      SELECT 1 FROM pg_depend d
      JOIN pg_extension e ON e.oid = d.refobjid
      WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
    )
  UNION ALL
  SELECT t.oid
  FROM pg_type t
  JOIN pg_namespace n ON n.oid = t.typnamespace
  WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd')
    AND t.typowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)
    AND NOT EXISTS (
      SELECT 1 FROM pg_depend d
      JOIN pg_extension e ON e.oid = d.refobjid
      WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e'
    )
) AS ownership_violations;
SQL
)"
restore_ownership_violations="${restore_ownership_violations//$'\n'/}"
[[ "$restore_ownership_violations" == 0 ]] || {
  echo "Deployment refused: application objects are not fully owned by the runtime database role." >&2
  exit 2
}

state_file="$DEPLOY_ROOT/current.env"
state_previous_commit=""
if [[ -f "$state_file" ]]; then
  [[ ! -L "$state_file" ]] || {
    echo "Deployment state file must not be a symlink." >&2
    exit 2
  }
  state_previous_commit="$(awk -F= '$1 == "deployed_commit" {print $2}' "$state_file")"
fi
if [[ -n "$provided_previous_commit" && -n "$state_previous_commit" && "$provided_previous_commit" != "$state_previous_commit" ]]; then
  echo "Provided previous commit does not match recorded deployment state." >&2
  exit 2
fi
previous_commit="${state_previous_commit:-$provided_previous_commit}"
[[ "$previous_commit" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "The first guarded deployment requires --previous-commit with the deployed 40-character commit." >&2
  exit 2
}
git cat-file -e "$previous_commit^{commit}"

previous_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
previous_revision="${previous_revision//$'\n'/}"
[[ "$previous_revision" =~ ^[A-Za-z0-9_]+$ ]] || {
  echo "Unable to establish the current production Alembic revision safely." >&2
  exit 2
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence_dir="$DEPLOY_ROOT/${timestamp}-${target_commit:0:12}"
mkdir "$evidence_dir"
chmod 700 "$evidence_dir"
metadata="$evidence_dir/metadata.env"
{
  printf 'target_commit=%s\n' "$target_commit"
  printf 'previous_commit=%s\n' "$previous_commit"
  printf 'target_revision=%s\n' "$EXPECTED_REVISION"
  printf 'previous_revision=%s\n' "$previous_revision"
  printf 'started_at=%s\n' "$timestamp"
} >"$metadata"
chmod 600 "$metadata"

snapshot="$evidence_dir/tibiahub.dump"
postgres_exec pg_dump --format=custom --no-owner --no-acl --file="$snapshot"
chmod 600 "$snapshot"
[[ -f "$snapshot" && ! -L "$snapshot" ]] || {
  echo "The production snapshot was not created as a regular file." >&2
  exit 1
}
pg_restore --list "$snapshot" >"$evidence_dir/tibiahub.dump.list"
chmod 600 "$evidence_dir/tibiahub.dump.list"
awk '!/ EXTENSION / && !/ TABLE DATA public spatial_ref_sys /' \
  "$evidence_dir/tibiahub.dump.list" >"$evidence_dir/tibiahub.restore.list"
chmod 600 "$evidence_dir/tibiahub.restore.list"
[[ -s "$evidence_dir/tibiahub.restore.list" ]] || {
  echo "The extension-preserving restore catalog is empty." >&2
  exit 1
}
sha256sum "$snapshot" >"$evidence_dir/tibiahub.dump.sha256"
chmod 600 "$evidence_dir/tibiahub.dump.sha256"

if [[ -d "$ROOT/frontend/dist" ]]; then
  cp -a "$ROOT/frontend/dist" "$evidence_dir/frontend-dist-current"
  touch "$evidence_dir/frontend-dist-current.present"
else
  touch "$evidence_dir/frontend-dist-current.absent"
fi

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

previous_worktree=""
cleanup_previous_worktree() {
  if [[ -n "$previous_worktree" && -d "$previous_worktree" ]]; then
    git worktree remove --force "$previous_worktree" >/dev/null 2>&1 || true
  fi
}
trap cleanup_previous_worktree EXIT
previous_worktree="$evidence_dir/previous-worktree"
git worktree add --quiet --detach "$previous_worktree" "$previous_commit"
[[ -d "$ROOT/frontend/node_modules" ]] || {
  echo "Frontend dependencies are required to construct the rollback build." >&2
  exit 1
}
ln -s "$ROOT/frontend/node_modules" "$previous_worktree/frontend/node_modules"
(cd "$previous_worktree/frontend" && npm run build -- --outDir "$evidence_dir/frontend-dist-previous")
[[ -f "$evidence_dir/frontend-dist-previous/index.html" ]] || {
  echo "The previous-commit frontend rollback build is incomplete." >&2
  exit 1
}
git worktree remove --force "$previous_worktree"
previous_worktree=""

staged_dist="$evidence_dir/frontend-dist-new"
(cd "$ROOT/frontend" && npm run build -- --outDir "$staged_dist")
[[ -f "$staged_dist/index.html" ]] || {
  echo "The staged frontend build is incomplete." >&2
  exit 1
}

rollback_armed=0
on_error() {
  local exit_code=$?
  trap - ERR
  printf 'failed_at=%s\nexit_code=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$exit_code" >"$evidence_dir/FAILED"
  chmod 600 "$evidence_dir/FAILED"
  if [[ "$rollback_armed" == 1 ]]; then
    if TIBIAHUB_DEPLOY_LOCK_HELD=1 "$ROOT/deploy/scripts/rollback.sh" \
      --confirm-rollback-tibiahub "$evidence_dir"; then
      touch "$evidence_dir/ROLLBACK_SUCCEEDED"
    else
      touch "$evidence_dir/ROLLBACK_FAILED"
    fi
  fi
  echo "Deployment failed; evidence was preserved at $evidence_dir" >&2
  exit "$exit_code"
}
trap on_error ERR

rollback_armed=1
for service in "${SERVICES[@]}"; do
  if pm2 describe "$service" >/dev/null 2>&1; then
    pm2 stop "$service"
  fi
done

run_alembic upgrade head
resulting_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
resulting_revision="${resulting_revision//$'\n'/}"
[[ "$resulting_revision" == "$EXPECTED_REVISION" ]] || {
  echo "Production did not reach the expected Alembic revision." >&2
  false
}

if [[ -e "$ROOT/frontend/dist" && ! -d "$ROOT/frontend/dist" ]]; then
  echo "Refusing to replace a non-directory frontend dist path." >&2
  false
fi
rm -rf -- "$ROOT/frontend/dist"
mv "$staged_dist" "$ROOT/frontend/dist"

pm2_start_service() {
  env -i \
    HOME="$HOME" USER="${USER:-}" PATH="$PATH" PM2_HOME="${PM2_HOME:-$HOME/.pm2}" \
    pm2 startOrReload "$ROOT/ecosystem.config.js" --only "$1" --update-env
}
for service in "${SERVICES[@]}"; do pm2_start_service "$service"; done

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

for url in "${LOCAL_URLS[@]}"; do wait_for_url "$url"; done
for url in "${PUBLIC_URLS[@]}"; do wait_for_url "$url"; done
for service in "${SERVICES[@]}"; do
  pm2 jlist | jq -e --arg name "$service" \
    'any(.[]; .name == $name and .pm2_env.status == "online")' >/dev/null
done
worker_heartbeat_count="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 <<'SQL'
SELECT
  (SELECT EXISTS (SELECT 1 FROM raffle_scheduler_state WHERE heartbeat_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM knowledge_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM email_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int
  + (SELECT EXISTS (SELECT 1 FROM sync_worker_heartbeats WHERE last_seen_at >= now() - interval '5 minutes'))::int;
SQL
)"
worker_heartbeat_count="${worker_heartbeat_count//$'\n'/}"
[[ "$worker_heartbeat_count" == 4 ]] || {
  echo "One or more TibiaHub worker heartbeats are stale or missing." >&2
  false
}

[[ "$(git branch --show-current)" == "develop" ]]
[[ -z "$(git status --porcelain --untracked-files=all)" ]]
[[ "$(git rev-parse HEAD)" == "$target_commit" ]]
[[ "$(git rev-parse refs/remotes/origin/develop)" == "$target_commit" ]]

completed_at="$(date -u +%Y%m%dT%H%M%SZ)"
state_tmp="$DEPLOY_ROOT/.current.env.$$"
{
  printf 'deployed_commit=%s\n' "$target_commit"
  printf 'alembic_revision=%s\n' "$EXPECTED_REVISION"
  printf 'snapshot_dir=%s\n' "$evidence_dir"
  printf 'deployed_at=%s\n' "$completed_at"
} >"$state_tmp"
chmod 600 "$state_tmp"
mv "$state_tmp" "$state_file"
printf 'completed_at=%s\n' "$completed_at" >>"$metadata"
touch "$evidence_dir/SUCCEEDED"
trap - ERR
trap - EXIT

snapshot_sha256="$(awk '{print $1}' "$evidence_dir/tibiahub.dump.sha256")"
echo "Deployment succeeded."
echo "Target commit: $target_commit"
echo "Previous commit: $previous_commit"
echo "Previous Alembic revision: $previous_revision"
echo "Resulting Alembic revision: $resulting_revision"
echo "Snapshot directory: $evidence_dir"
echo "Snapshot SHA-256: $snapshot_sha256"
