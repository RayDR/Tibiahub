#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "rebuild-spatial-links.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

case "${1:-}" in
  --dry-run)
    [[ $# -eq 1 ]] || { echo "Usage: $0 --dry-run | --execute --confirm-rebuild-spatial-links" >&2; exit 2; }
    mode=--dry-run
    ;;
  --execute)
    [[ $# -eq 2 && "${2:-}" == "--confirm-rebuild-spatial-links" ]] || { echo "Execution requires --execute --confirm-rebuild-spatial-links" >&2; exit 2; }
    mode=--execute
    ;;
  *)
    echo "Usage: $0 --dry-run | --execute --confirm-rebuild-spatial-links" >&2
    exit 2
    ;;
esac
load_tibiahub_environment
require_local_tibiahub_target
if [[ "$mode" == "--execute" ]]; then
  PYTHONPATH="$TIBIAHUB_BACKEND" APP_ENV="${APP_ENV:-production}" "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/rebuild-spatial-links.py" --execute
else
  PYTHONPATH="$TIBIAHUB_BACKEND" APP_ENV="${APP_ENV:-production}" "$TIBIAHUB_BACKEND/venv/bin/python" "$TIBIAHUB_ROOT/scripts/rebuild-spatial-links.py"
fi
