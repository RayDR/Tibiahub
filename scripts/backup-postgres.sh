#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
	echo "backup-postgres.sh must be executed, not sourced." >&2
	return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

load_tibiahub_environment
require_local_tibiahub_target
backup_dir="${TIBIAHUB_BACKUP_DIR:-/var/backups/tibiahub}"
mkdir -p "$backup_dir"
backup_path="${1:-$backup_dir/tibiahub-$(date -u +%Y%m%dT%H%M%SZ).dump}"
postgres_exec pg_dump --format=custom --no-owner --no-acl --file="$backup_path"
chmod 600 "$backup_path"
echo "Backup written to $backup_path"
