#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/postgres-common.sh"

load_tibiahub_environment
require_local_tibiahub_target
backup_dir="${TIBIAHUB_BACKUP_DIR:-/var/backups/tibiahub}"
mkdir -p "$backup_dir"
backup_path="${1:-$backup_dir/tibiahub-$(date -u +%Y%m%dT%H%M%SZ).dump}"
postgres_exec pg_dump --format=custom --no-owner --no-acl --file="$backup_path"
chmod 600 "$backup_path"
echo "Backup written to $backup_path"
