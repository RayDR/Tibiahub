#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "restore-postgres.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

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
postgres_exec pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl "$backup_path"
run_alembic upgrade head
echo "Restore completed for the configured TibiaHub database only."
