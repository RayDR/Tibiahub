#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/postgres-common.sh"

case "${1:-}" in
  --dry-run)
    [[ $# -eq 1 ]] || { echo "Usage: $0 --dry-run | --execute --confirm-tibiahub" >&2; exit 2; }
    mode=--dry-run
    ;;
  --execute)
    [[ $# -eq 2 && "${2:-}" == "--confirm-tibiahub" ]] || { echo "Execution requires --execute --confirm-tibiahub" >&2; exit 2; }
    mode=--execute
    ;;
  *)
    echo "Usage: $0 --dry-run | --execute --confirm-tibiahub" >&2
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
