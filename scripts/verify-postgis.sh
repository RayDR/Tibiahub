#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "verify-postgis.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$SCRIPT_DIR/lib/postgres.sh"

if [[ "${1:-}" != "--dry-run" || $# -ne 1 ]]; then
  echo "Usage: $0 --dry-run" >&2
  exit 2
fi
load_tibiahub_environment
require_local_tibiahub_target
postgres_exec psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT current_database() AS database_name, current_user AS application_role;
SELECT extversion AS postgis_version FROM pg_extension WHERE extname='postgis';
DO $tibiahub$
BEGIN
  IF current_database() <> 'tibiahub' THEN
    RAISE EXCEPTION 'PostGIS verification is restricted to tibiahub';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis') THEN
    RAISE EXCEPTION 'PostGIS is not installed in the TibiaHub database';
  END IF;
END
$tibiahub$;
SELECT ST_AsText(ST_SetSRID(ST_MakePoint(32369,32241,7),0)) AS three_dimensional_probe;
SQL
echo "PostGIS verification passed without modifying data."
