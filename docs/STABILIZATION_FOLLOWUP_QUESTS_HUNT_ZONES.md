# Stabilization Follow-up: Quests and Hunt Zones

This note tracks medium-term improvements intentionally deferred during the current stabilization pass.

## Quests

- Improve ranking quality for short or ambiguous queries (alias support and mission-name matching).
- Add optional quest chain grouping to reduce duplicate-like entries.
- Add richer local metadata in sync output for objectives and required items.
- Keep public list/search local-first (DB/cache only) and route all enrichments through sync/admin jobs.

## Hunt Zones

- Normalize map image metadata and source quality scoring during sync.
- Add lightweight map/image health checks to identify stale or broken map links.
- Improve zone recommendation summaries (creature density, average spawn overlap, profit context).
- Keep map rendering resilient: local proxy first, graceful fallback map when image is unavailable.

## Operational Guardrails

- Continue treating external APIs as sync-only dependencies, not real-time request dependencies for public browsing.
- Keep image auto-fetch disabled by default in production; enable only during controlled recovery windows.
- Validate with cURL matrix and frontend build after each stabilization patch set.
