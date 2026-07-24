# TibiaHub Knowledge Graph Core

Stage 2B-1 introduces one provider-neutral relationship model. It is intentionally limited to depth-one traversal and the Creature, Item, and Quest knowledge already imported by Stage 2A.

## Authority and compatibility

`knowledge_relationship_types` and `knowledge_relationships` are authoritative for new relationship writes and graph reads. The Creature/Item `knowledge_creature_item_drops` and Quest `knowledge_quest_relations` tables remain compatibility mirrors while existing contracts are preserved. The migration copies their current facts idempotently and does not drop or rewrite them. Adapters write through the graph service and temporarily maintain those compatibility rows. Item drop and Quest relationship detail responses now read the graph; Creature's established loot contract remains a compatibility presentation alongside the entity graph endpoint.

The graph stores one canonical direction. Incoming traversal derives the registered inverse, so a Creature `drops` Item fact is not duplicated as an Item `dropped_by` Creature row. Mission facts retain their source quest plus a mission scope.

## Type and provenance rules

Relationship codes are stable and language-neutral. The registry owns allowed source/target entity types, inverse codes, visibility, direction, symmetry, and transitivity. Display text is provided by the `knowledgeGraph.relationships.*` English and Spanish translation keys.

Provider facts are unique per source, scope, type, target identity, and provider provenance. Multiple providers can support the same logical fact and the public DTO consolidates them. A manually verified fact takes precedence, while provider history remains auditable. Provider reconciliation is opt-in and may supersede only the selected provider's non-manual current facts; it never removes verified facts merely because an import omitted them.

Unresolved and ambiguous references retain a normalized name and may include existing candidate UUIDs in protected source context. Candidate lists are admin-only. Resolution must select an existing entity, pass registry type validation, include a reason, create a verified successor, and preserve the old record as superseded history.

## APIs

Public local-only depth-one reads:

- `GET /api/v1/knowledge/entities/{entity_id}/relationships`
- `GET /api/v1/knowledge/entities/{entity_id}/relationships/outgoing`
- `GET /api/v1/knowledge/entities/{entity_id}/relationships/incoming`

All are paginated and optionally filter by `relationship_type`. They never expose raw provider documents, source context, candidate lists, secrets, or internal user IDs. Ambiguous facts are excluded.

Global-admin review lives under `/api/v1/admin/knowledge/relationships`. It supports unresolved/ambiguous listing, safe provenance, resolution, rejection, verification, and explicit supersession. Mutations write workspace audit records.

## Safe utilities

- `scripts/verify-knowledge-graph.py --dry-run` performs read-only registry and graph checks.
- `scripts/rebuild-knowledge-relationships.py --dry-run` reports eligible compatibility facts. Mutation additionally requires `--confirm-rebuild-knowledge-relationships`.
- `scripts/resolve-knowledge-reference.py --dry-run ...` validates one existing target. Mutation additionally requires `--confirm-resolve-knowledge-reference`.

Every utility uses shared settings, refuses a database whose exact name is not `tibiahub`, and does not print credentials. No utility executes automatically during migration or deployment.

## Deferred work

Full NPC and Location ingestion, map geometry/PostGIS, recursive paths, unified search, media ingestion, embeddings/vector search, and AI consumers remain outside Stage 2B-1.
