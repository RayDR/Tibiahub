#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/postgres-common.sh"

if [[ "${1:-}" != "--confirm-restore-tibiahub" || $# -ne 2 ]]; then
  echo "Usage: $0 --confirm-restore-tibiahub /absolute/path/to/backup.dump" >&2
  exit 2
fi

backup_path="$2"
if [[ ! -f "$backup_path" ]]; then
  echo "Backup file does not exist." >&2
  exit 2
fi
load_tibiahub_environment
require_local_tibiahub_target
pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl --dbname="$(libpq_url "$DATABASE_URL")" "$backup_path"
run_alembic upgrade head
echo "Restore completed for the configured TibiaHub database only."
