# Knowledge NPC and Location Adapters

This stage imports TibiaWiki NPC and named-location pages through the durable Knowledge worker. TibiaWiki remains disabled by default, no jobs are scheduled automatically, and every catalog run requires an explicit batch size from 1 to 50 plus confirmation.

## Jobs and source boundaries

`npc_catalog` and `location_catalog` read one continuation-token page from `Category:NPCs` and `Category:Locations`. They store the raw response and enqueue bounded, idempotent detail children. `npc_detail` and `location_detail` import one numeric MediaWiki page ID (or a page title for discovery). The corresponding `*_renormalize` jobs replay the latest immutable detail document without a provider request.

Unknown provider fields remain only in `knowledge_documents.raw_json`. Executable markup, invalid envelopes, invalid numeric ranges, oversized responses, and identity-only partial pages are rejected or retained without overwriting canonical data. Provider markup never reaches the local read APIs.

## Canonical ownership and identity

Identity is provider + entity type + numeric MediaWiki page ID. An existing external mapping wins; otherwise only an exact normalized canonical name or approved alias may be reused. Fuzzy matching is prohibited, and same-name provider variants remain separate canonical entities.

The bridges `tibiawiki_npcs` and `tibiawiki_locations` contain queryable, provider-neutral fields. Protected fields are locally owned. Missing or empty provider values cannot erase populated data. Version numbers change only for canonical field changes, not for sync timestamps.

NPC records include title, occupation, sex, named location, description, trade lists, destinations, and related quests. Location records include kind, region, parent name, description, premium and level guidance, named NPC/creature/quest/sublocation lists, and access notes. Coordinates, geometry, map tiles, routes, and media downloads are deliberately outside this stage.

## Graph resolution

Quest NPC and Location references created by Stage 2A-5 are resolved when exactly one canonical name or approved alias matches an imported entity. Resolution creates a provenance-preserving current graph fact and supersedes the unresolved fact. Multiple exact candidates remain ambiguous for admin review; no guess or new target is created.

## Local APIs and operations

- `GET /api/v1/npcs/` and `GET /api/v1/npcs/{identifier}`
- `GET /api/v1/locations/` and `GET /api/v1/locations/{identifier}`

Identifiers may be a local row ID, numeric provider page ID, slug, or exact normalized name. These endpoints read PostgreSQL only and exclude raw documents and provider metadata.

The Knowledge Operations UI and safe enqueue CLI expose catalog, detail, and renormalize jobs in English and Spanish. Example one-page dry runs:

```bash
backend/venv/bin/python scripts/enqueue-knowledge-job.py --dry-run \
  --provider tibiawiki --entity-type npc --job-type npc_detail \
  --external-id 800 --npc-name Angus

backend/venv/bin/python scripts/enqueue-knowledge-job.py --dry-run \
  --provider tibiawiki --entity-type location --job-type location_detail \
  --external-id 900 --location-name "Port Hope"
```

Production provider enablement and import execution require a separate operational decision after deployment validation.
