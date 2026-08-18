# TibiaHub Knowledge Graph Core

Stage 2B-1 introduces one provider-neutral relationship model. It is intentionally limited to depth-one traversal and the Creature, Item, and Quest knowledge already imported by Stage 2A.

## Authority and compatibility

`knowledge_relationship_types` and `knowledge_relationships` are authoritative for new relationship writes and graph reads. The Creature/Item `knowledge_creature_item_drops` and Quest `knowledge_quest_relations` tables remain read-only compatibility sources while existing contracts are preserved. The migration copies their current facts idempotently and does not drop or rewrite them. Adapters write only through the graph service. Item drop and Quest relationship detail responses read the graph; Creature's established loot contract remains a compatibility presentation alongside the entity graph endpoint.

The graph stores one canonical direction. Incoming traversal derives the registered inverse, so a Creature `drops` Item fact is not duplicated as an Item `dropped_by` Creature row. Mission facts retain their source quest plus a mission scope.

## Type and provenance rules

Relationship codes are stable and language-neutral. The registry owns allowed source/target entity types, inverse codes, visibility, direction, symmetry, and transitivity. Display text is provided by the `knowledgeGraph.relationships.*` English and Spanish translation keys.

Provider facts are unique per source, scope, type, target identity, and provider provenance. Multiple providers can support the same logical fact and the public DTO consolidates them. A manually verified fact takes precedence, while provider history remains auditable. Provider reconciliation is opt-in and may supersede only the selected provider's non-manual current facts; it never removes verified facts merely because an import omitted them.

## P0 closure reconciliation

`scripts/reconcile-knowledge-layer.py` is the bounded closure pass for existing
facts. `--dry-run` reports exact-name/approved-alias candidates and deterministic
raw-document links without changing PostgreSQL. Mutation requires both `--apply`
and the exact confirmation phrase printed by the command help. The pass never
uses fuzzy matching, never creates entities or provider documents, never fills
unknown canonical fields, and never changes manual overrides. A successful
apply runs the same pass again in its transaction and reports zero resolved
facts and zero repaired provenance links in `second_pass`.

Run it only after loading the production environment and validating the local
target with `scripts/lib/postgres.sh`, as required for all production database
operations.

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

NPC and Location ingestion is provided by the following adapter stage. Map geometry/PostGIS, recursive paths, unified search, media ingestion, embeddings/vector search, and AI consumers remain deferred.
