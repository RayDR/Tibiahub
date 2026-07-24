# Creature Knowledge Adapter

Stage 2A-3 connects TibiaHub's existing TibiaWiki ingestion source to the durable Knowledge Platform. It deliberately covers creatures only. The provider is registered disabled and no job is enqueued at application or worker startup.

## Existing-source audit

The current creature catalog and detail source is the MediaWiki API configured by `TIBIAWIKI_API_URL` in `bestiary_source.py`:

- Catalog: MediaWiki `categorymembers` for `Category:Creatures`, with `cmcontinue` pagination.
- Detail: MediaWiki `parse` with `prop=wikitext`, addressed by stable page ID when available and title otherwise.
- Identity: legacy rows used a CRC32 of the normalized name. The adapter instead uses MediaWiki `pageid`, which is stable and is never derived from result order.
- Existing capture: official name/article/plural, HP, experience, armor, speed, maximum damage, summon/convince costs, bestiary class/level, charm points, occurrence/difficulty/classification, boss flag, descriptions, behavior, image reference, loot references, locations, and task references.
- Existing loss: the legacy parser reduced the response to business fields. The adapter stores the complete provider envelope and wikitext as an immutable `KnowledgeDocument`, retaining unrecognized fields for replay.
- Media: only provider page and sprite URL references are retained. This stage never downloads media.
- Localization: the provider's official English creature names are preserved. The adapter does not fabricate translated creature names.
- Legacy behavior: bestiary calls used shared HTTP timeout, cache, retry, and circuit-breaker helpers; sync operations used `SyncJob` batches and checkpoints. A creature-detail request could fall back to a live provider fetch. Stage 2A-3 removes that request-time fallback for list/detail reads.

TibiaData remains used elsewhere in TibiaHub, but the inspected code does not use it as the full creature catalog/detail source. The adapter is therefore registered as `tibiawiki`.

## Durable import flow

`creature_catalog` requires an explicit batch limit from 1 to 50. It stores the raw catalog envelope, creates one idempotent `creature_detail` child per valid page, and creates a bounded continuation child when MediaWiki returns `cmcontinue`. Children inherit the parent correlation ID. The provider cursor and child jobs commit in the same transaction as the raw catalog document and completed attempt.

`creature_detail` stores the full parse envelope, validates it, maps it to `CreatureKnowledgeDTO`, and then updates the canonical entity and current Cyclopedia row. A failed child is isolated from completed siblings. Standard worker retry, lease recovery, and provider cooldown behavior applies. Before each external TibiaWiki request, the worker locks the provider row and durably defers the claimed job when the configured request/window interval has not elapsed; deferred work creates no failed attempt and can be claimed after its new schedule.

`creature_renormalize` loads the latest stored `creature:<pageid>` document and performs no provider request. It is useful when normalization code changes.

Catalog jobs are not full-sync defaults. They require an explicit batch size plus confirmation in the admin API/UI. The CLI supports dry-run and confirmation. No startup hook enqueues work.

## Validation and raw retention

The adapter classifies results as `valid`, `partial`, `invalid`, `empty`, `provider_error`, or `oversized`. It requires the expected MediaWiki envelope, stable page ID, official nonempty title/name, nonempty wikitext, supported type shapes, and nonnegative bounded numeric values. It rejects unsafe script/event-handler or `javascript:` content and limits serialized payloads to 2 MiB. Provider failures are converted to safe worker failure codes; response bodies and credentials are not logged or stored as operational metadata.

Unknown fields stay only in `knowledge_documents.raw_json`. Partial detail documents are retained and their jobs are marked partial, but insufficient detail is not normalized and cannot supersede a valid canonical record.

## Identity and bridge rules

Identity resolution is intentionally conservative:

1. Resolve `(provider=tibiawiki, entity_type=creature, external_id=pageid)` in `knowledge_external_mappings`.
2. If absent, resolve an exact normalized canonical name or approved existing alias.
3. Otherwise create a permanent `KnowledgeEntity` UUID and mapping.

Fuzzy similarity never merges entities. Alias uniqueness is enforced per entity type. Conflicting mappings and Creature/Boss mismatches fail normalization rather than guessing. Database constraints prevent duplicate provider mappings and multiple `Creature` rows pointing at one KnowledgeEntity.

The bridge may associate a legacy Creature only by an existing knowledge link, the exact TibiaWiki external ID, or exact normalized name. It does not delete unmatched rows. It keeps raw provider JSON out of the business table and sets `knowledge_entity_id`, provider provenance, supported Cyclopedia fields, loot references, aliases, and search metadata. `data_version` increases only when canonical Creature/loot data changes; freshness can change without incrementing the version.

## Field precedence and protection

TibiaWiki priority is 20. It owns supplied current stats, bestiary metadata, official description/behavior, loot/location/task references, and source/image references. Missing, null, or empty provider values never erase populated values. Insufficient partial detail never normalizes.

Local/admin ownership is represented by the small `Creature.protected_fields` list and the existing `image_locked` flag. A protected field is never overwritten by this provider. This covers editorial/admin corrections without introducing a broad rules engine. Existing unmatched or ambiguous data is left unchanged and the import reports a conflict.

## Local reads and intentionally remaining provider calls

`GET /api/v1/creatures` and `GET /api/v1/creatures/{identifier}` query PostgreSQL only, preserve the current response shape, return stored image references, expose the linked KnowledgeEntity/data version, and include safe freshness metadata when present. A missing local creature returns 404 even if the provider is available; provider health does not affect a cached read.

Direct provider access intentionally remains in explicit legacy/admin synchronization services and the existing optional image lookup endpoint. Those paths are outside user-facing creature list/detail reads and are not started by this stage.

## Controlled one-creature smoke

Do not enable the provider or worker until production is PostgreSQL and Alembic is at `knowledge_creature_20260723`. Then, in a controlled environment:

1. Enable only the registered `tibiawiki` provider and explicitly start one Knowledge worker.
2. Dry-run a detail job: `python scripts/enqueue-knowledge-job.py --provider tibiawiki --entity-type creature --job-type creature_detail --external-id <MEDIAWIKI_PAGE_ID> --creature-name <OFFICIAL_NAME> --dry-run`.
3. Re-run with `--confirm-enqueue-knowledge-job`, record the job ID, and wait for that one job only.
4. Verify one raw document, one external mapping, one KnowledgeEntity, one linked Creature, aliases/search metadata, and a successful attempt without secrets in metadata/logs.
5. Disable the provider/worker again if broader imports are not explicitly approved. Never use a catalog job for the smoke.

Items, quests, NPCs, maps, media downloading, unified search UI, embeddings, pgvector, AI, and Knowledge Graph relationships remain deferred.
