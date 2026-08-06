#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "reset-postgres.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

if [[ "${1:-}" != "--confirm-reset-tibiahub" || $# -ne 1 ]]; then
  echo "Usage: $0 --confirm-reset-tibiahub" >&2
  exit 2
fi

load_tibiahub_environment
require_local_tibiahub_target
load_postgres_admin_environment

database_name="$(database_component name)"
application_role="${TIBIAHUB_DATABASE_ROLE:-tibiahub_app}"
legacy_sqlite="$TIBIAHUB_BACKEND/tibia_bestiary.db"
backup_dir="${TIBIAHUB_BACKUP_DIR:-/var/backups/tibiahub}"

if [[ -f "$legacy_sqlite" ]]; then
  mkdir -p "$backup_dir"
  backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "$legacy_sqlite" "$backup_dir/tibia_bestiary-pre-postgres-$backup_stamp.db"
  echo "Preserved the legacy SQLite file outside the repository; the original was not deleted."
fi

if [[ "${STOP_TIBIAHUB_SERVICES:-0}" == "1" ]] && command -v pm2 >/dev/null 2>&1; then
  pm2 stop tibiahub-raffle-scheduler tibiahub-api || true
fi

require_postgres_admin_access
postgres_admin_dropdb --if-exists --force "$database_name"
postgres_admin_createdb --owner="$application_role" "$database_name"
run_alembic upgrade head

if [[ -n "${BOOTSTRAP_ADMIN_USERNAME:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" || -n "${BOOTSTRAP_ADMIN_EMAIL:-}" ]]; then
  : "${BOOTSTRAP_ADMIN_USERNAME:?All BOOTSTRAP_ADMIN_* values are required}"
  : "${BOOTSTRAP_ADMIN_PASSWORD:?All BOOTSTRAP_ADMIN_* values are required}"
  : "${BOOTSTRAP_ADMIN_EMAIL:?All BOOTSTRAP_ADMIN_* values are required}"
  PYTHONPATH="$TIBIAHUB_BACKEND" "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/bootstrap_admin.py"
fi

echo "Reset completed for the configured TibiaHub database only."
