#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "bootstrap-admin.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

bootstrap_secrets_file="${TIBIAHUB_BOOTSTRAP_SECRETS_FILE:-/forge/tibiahub-secrets/bootstrap.env}"
load_tibiahub_environment
require_local_tibiahub_target
load_secure_file "$bootstrap_secrets_file" "TibiaHub bootstrap secret file"
: "${BOOTSTRAP_ADMIN_USERNAME:?BOOTSTRAP_ADMIN_USERNAME is required}"
: "${BOOTSTRAP_ADMIN_PASSWORD:?BOOTSTRAP_ADMIN_PASSWORD is required}"
: "${BOOTSTRAP_ADMIN_EMAIL:?BOOTSTRAP_ADMIN_EMAIL is required}"

PYTHONPATH="$TIBIAHUB_BACKEND" APP_ENV="${APP_ENV:-production}" \
  "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/bootstrap_admin.py"
