#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "verify-spatial-consistency.sh must be executed, not sourced." >&2
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
DO $tibiahub$
BEGIN
  IF current_database() <> 'tibiahub' THEN
    RAISE EXCEPTION 'Spatial verification is restricted to tibiahub';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis') THEN
    RAISE EXCEPTION 'PostGIS is not installed in the TibiaHub database';
  END IF;
END
$tibiahub$;
SELECT 'invalid_points' AS check_name, count(*) AS failures
FROM spatial_map_points
WHERE is_current AND geom IS NOT NULL
  AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3 OR tibia_z NOT BETWEEN 0 AND 15
       OR ST_X(geom) <> tibia_x OR ST_Y(geom) <> tibia_y OR ST_Z(geom) <> tibia_z)
UNION ALL
SELECT 'invalid_regions', count(*) FROM spatial_map_regions
WHERE is_current AND geom IS NOT NULL AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3)
UNION ALL
SELECT 'invalid_routes', count(*) FROM spatial_routes
WHERE is_current AND geom IS NOT NULL AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3)
UNION ALL
SELECT 'route_step_count_mismatch', count(*) FROM spatial_routes route
WHERE route.is_current AND route.step_count <> (SELECT count(*) FROM spatial_route_steps step WHERE step.route_id=route.id)
UNION ALL
SELECT 'orphan_current_links', count(*) FROM spatial_entity_location_links link
WHERE link.is_current AND link.location_entity_id IS NULL AND link.unresolved_location_name IS NULL;
DO $tibiahub$
BEGIN
  IF EXISTS (
    SELECT 1 FROM spatial_map_points
    WHERE is_current AND geom IS NOT NULL
      AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3 OR tibia_z NOT BETWEEN 0 AND 15
           OR ST_X(geom) <> tibia_x OR ST_Y(geom) <> tibia_y OR ST_Z(geom) <> tibia_z)
  ) OR EXISTS (
    SELECT 1 FROM spatial_map_regions
    WHERE is_current AND geom IS NOT NULL AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3)
  ) OR EXISTS (
    SELECT 1 FROM spatial_routes
    WHERE is_current AND geom IS NOT NULL AND (NOT ST_IsValid(geom) OR ST_NDims(geom) <> 3)
  ) OR EXISTS (
    SELECT 1 FROM spatial_routes route
    WHERE route.is_current
      AND route.step_count <> (SELECT count(*) FROM spatial_route_steps step WHERE step.route_id=route.id)
  ) OR EXISTS (
    SELECT 1 FROM spatial_entity_location_links link
    WHERE link.is_current AND link.location_entity_id IS NULL AND link.unresolved_location_name IS NULL
  ) THEN
    RAISE EXCEPTION 'Spatial consistency validation failed';
  END IF;
END
$tibiahub$;
SQL
echo "Spatial consistency dry-run completed without modifying data."
