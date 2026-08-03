#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/postgres-common.sh
source "$ROOT/scripts/postgres-common.sh"

DEPLOY_ROOT="${TIBIAHUB_DEPLOY_ROOT:-/forge/tibiahub-backups/deployments}"
LOCK_FILE="${TIBIAHUB_DEPLOY_LOCK_FILE:-$DEPLOY_ROOT/.deploy.lock}"
SERVICES=(
  tibiahub-api
  tibiahub-frontend
  tibiahub-raffle-scheduler
  tibiahub-knowledge-worker
)

if [[ "${1:-}" != "--confirm-rollback-tibiahub" || $# -ne 2 ]]; then
  echo "Usage: $0 --confirm-rollback-tibiahub /absolute/deployment/evidence-directory" >&2
  exit 2
fi
requested_evidence="$2"

[[ "$DEPLOY_ROOT" == /* && -d "$DEPLOY_ROOT" && ! -L "$DEPLOY_ROOT" ]] || {
  echo "Deployment root must be an absolute, non-symlink directory." >&2
  exit 2
}
deploy_root_mode="$(stat -c '%a' "$DEPLOY_ROOT")"
[[ "$(stat -c '%u' "$DEPLOY_ROOT")" == "$(id -u)" && $((8#$deploy_root_mode & 077)) -eq 0 ]] || {
  echo "Deployment root must be owned by the deployment user and private." >&2
  exit 2
}
[[ "$LOCK_FILE" == /* && "$(dirname "$LOCK_FILE")" == "$DEPLOY_ROOT" && ! -L "$LOCK_FILE" ]] || {
  echo "Deployment lock must be a non-symlink file inside the deployment root." >&2
  exit 2
}
if [[ "${TIBIAHUB_DEPLOY_LOCK_HELD:-0}" != 1 ]]; then
  exec 9>"$LOCK_FILE"
  chmod 600 "$LOCK_FILE"
  if ! flock -n 9; then
    echo "Another TibiaHub deployment or rollback holds the deployment lock." >&2
    exit 2
  fi
fi

[[ "$requested_evidence" == /* && -d "$requested_evidence" && ! -L "$requested_evidence" ]] || {
  echo "Rollback requires an absolute, regular evidence directory." >&2
  exit 2
}
evidence_dir="$(realpath -e "$requested_evidence")"
deploy_root_real="$(realpath -e "$DEPLOY_ROOT")"
[[ "$evidence_dir" == "$deploy_root_real"/* && "$(dirname "$evidence_dir")" == "$deploy_root_real" ]] || {
  echo "Rollback evidence must be a direct child of the configured deployment root." >&2
  exit 2
}
[[ "$(stat -c '%u' "$evidence_dir")" == "$(id -u)" ]] || {
  echo "Rollback evidence must be owned by the deployment user." >&2
  exit 2
}

metadata="$evidence_dir/metadata.env"
snapshot="$evidence_dir/tibiahub.dump"
pm2_state="$evidence_dir/pm2-state.tsv"
for required_file in "$metadata" "$snapshot" "$evidence_dir/tibiahub.dump.sha256" "$pm2_state"; do
  [[ -f "$required_file" && ! -L "$required_file" ]] || {
    echo "Rollback evidence is incomplete." >&2
    exit 2
  }
done
[[ "$(stat -c '%a' "$snapshot")" == 600 ]] || {
  echo "Rollback snapshot permissions are not mode 0600." >&2
  exit 2
}
(cd "$evidence_dir" && sha256sum --check --status tibiahub.dump.sha256)
pg_restore --list "$snapshot" >/dev/null

metadata_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {print $2}' "$metadata"
}
previous_commit="$(metadata_value previous_commit)"
previous_revision="$(metadata_value previous_revision)"
[[ "$previous_commit" =~ ^[0-9a-fA-F]{40}$ && "$previous_revision" =~ ^[A-Za-z0-9_]+$ ]] || {
  echo "Rollback metadata is invalid." >&2
  exit 2
}

cd "$ROOT"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
  echo "Rollback requires a clean working tree." >&2
  exit 2
}
git cat-file -e "$previous_commit^{commit}"

load_tibiahub_environment
TIBIAHUB_DATABASE_NAME=tibiahub require_local_tibiahub_target
load_postgres_admin_environment
require_postgres_admin_access
database_name="$(database_component name)"
application_role="${TIBIAHUB_DATABASE_ROLE:-tibiahub_app}"
[[ "$database_name" == tibiahub && "$application_role" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
  echo "Rollback refused an unexpected database or application role." >&2
  exit 2
}

for service in "${SERVICES[@]}"; do
  if pm2 describe "$service" >/dev/null 2>&1; then
    pm2 stop "$service"
  fi
done

git switch --detach "$previous_commit"

postgres_admin_dropdb --if-exists --force "$database_name"
postgres_admin_createdb --owner="$application_role" "$database_name"
postgres_admin_psql -X -v ON_ERROR_STOP=1 -d "$database_name" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') THEN
    CREATE EXTENSION IF NOT EXISTS postgis;
  END IF;
END
$block$;
SQL

if [[ "$TIBIAHUB_POSTGRES_ADMIN_MODE" == peer ]]; then
  sudo -n -u postgres pg_restore \
    -p "${TIBIAHUB_DATABASE_PORT:-5432}" --dbname="$database_name" \
    --exit-on-error --no-owner --no-acl --role="$application_role" "$snapshot"
else
  pg_restore --dbname="$database_name" \
    --exit-on-error --no-owner --no-acl --role="$application_role" "$snapshot"
fi

restored_revision="$(postgres_exec psql -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
restored_revision="${restored_revision//$'\n'/}"
[[ "$restored_revision" == "$previous_revision" ]] || {
  echo "Rollback snapshot restored an unexpected Alembic revision." >&2
  exit 1
}

if [[ -e "$ROOT/frontend/dist" && ! -d "$ROOT/frontend/dist" ]]; then
  echo "Refusing to replace a non-directory frontend dist path." >&2
  exit 1
fi
rm -rf -- "$ROOT/frontend/dist"
if [[ -f "$evidence_dir/frontend-dist.present" ]]; then
  [[ -d "$evidence_dir/frontend-dist" ]] || {
    echo "Recorded frontend backup is missing." >&2
    exit 1
  }
  cp -a "$evidence_dir/frontend-dist" "$ROOT/frontend/dist"
fi

declare -A previous_status=()
while IFS=$'\t' read -r service status; do
  previous_status["$service"]="$status"
done <"$pm2_state"
for service in "${SERVICES[@]}"; do
  case "${previous_status[$service]:-absent}" in
    online)
      pm2 startOrReload "$ROOT/ecosystem.config.js" --only "$service" --update-env
      ;;
    absent)
      if pm2 describe "$service" >/dev/null 2>&1; then pm2 delete "$service"; fi
      ;;
    *)
      if pm2 describe "$service" >/dev/null 2>&1; then pm2 stop "$service"; fi
      ;;
  esac
done

rollback_at="$(date -u +%Y%m%dT%H%M%SZ)"
printf 'rolled_back_at=%s\nrestored_commit=%s\nrestored_revision=%s\n' \
  "$rollback_at" "$previous_commit" "$restored_revision" >"$evidence_dir/rollback.env"
chmod 600 "$evidence_dir/rollback.env"

state_tmp="$DEPLOY_ROOT/.current.env.$$"
{
  printf 'deployed_commit=%s\n' "$previous_commit"
  printf 'alembic_revision=%s\n' "$previous_revision"
  printf 'snapshot_dir=%s\n' "$evidence_dir"
  printf 'deployed_at=%s\n' "$rollback_at"
} >"$state_tmp"
chmod 600 "$state_tmp"
mv "$state_tmp" "$DEPLOY_ROOT/current.env"

echo "Rollback restored commit $previous_commit and Alembic revision $restored_revision."
echo "Rollback evidence remains at $evidence_dir"
