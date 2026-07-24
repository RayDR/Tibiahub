# Item Knowledge Adapter

Stage 2A-4 connects TibiaHub's existing TibiaWiki item source to the durable Knowledge Platform. It covers items and the first conservative Creature-to-Item drop relationship only. The provider remains registered but disabled, and neither application nor worker startup enqueues a job.

## Existing-source audit

The authoritative item source already configured by TibiaHub is the MediaWiki API selected by `TIBIAWIKI_API_URL` in `bestiary_source.py`:

- Catalog: MediaWiki `categorymembers` for `Category:Items`, using `cmcontinue` pagination.
- Detail: MediaWiki `parse` wikitext, addressed by stable `pageid` and optionally the official page title.
- Identity: the old catalog returned title-only summaries and item reads were reconstructed primarily from per-creature `Loot` rows. Those CRC32/name-derived legacy IDs are not provider identity. The adapter uses MediaWiki `pageid`; it never derives identity from result order.
- Existing capture: the legacy item bridge could store name, game item ID, description, broad type, basic combat/requirement fields, trade flags, and raw sync data, but the current catalog path supplied almost none of them. User item results mainly exposed loot chance/rarity and creature/hunt-zone context.
- Existing loss: detail envelopes and unrecognized infobox parameters were discarded or duplicated into mutable business rows. The adapter retains the complete envelope and wikitext in immutable `KnowledgeDocument.raw_json` and keeps only canonical fields in `tibiawiki_items`.
- Categories: the source exposes infobox `category`/`type` variants rather than a closed TibiaHub taxonomy. Values are preserved conservatively, and the original provider category and parameter names remain in document/provider metadata.
- Localization: official source names are retained; no translated item names or generated aliases are invented.
- Media: page and sprite URLs remain references only. No item media is downloaded by ingestion.
- Request-time calls: the old detail route could fetch a live item when the local row was incomplete. Item list/detail now read locally only. The optional image-cache route can still fetch a configured image reference when administrators have enabled missing-image autofetch; explicit legacy/admin sync tools also retain provider access.

## Durable flow and controls

`item_catalog` requires an explicit batch limit from 1 to 50. It stores one raw catalog envelope, creates idempotent `item_detail` children for valid item pages, and creates one bounded continuation child when the source supplies `cmcontinue`. Durable jobs retain parent and correlation IDs, the provider cursor, retry/lease behavior, partial counts, and persistent provider throttling already supplied by the Stage 2A worker.

`item_detail` stores and validates the complete parse response, maps supported fields into `ItemKnowledgeDTO`, then updates a canonical `KnowledgeEntity`, its mapping/search metadata, and one current `Item` row. Failed children remain isolated from successful siblings. `item_renormalize` replays the latest stored `item:<pageid>` document without network access. Incremental import is not exposed because this source integration does not currently provide a trustworthy incremental feed.

Catalog jobs require explicit confirmation in the API, UI, or CLI. Production `tibiawiki` stays disabled after migration. There is no implicit full sync, startup enqueue, arbitrary URL input, or second worker runtime.

## DTO, validation, and precedence

The provider-neutral DTO includes provider external ID, official name/slug/aliases, optional game item ID, class/type/category, weight/value and level/vocation requirements, combat values, slots/imbuement slots, attributes/resistances/bonuses, descriptions/notes, NPC references, creature drop references, reward/requirement references, trade flags, image/source references, provider metadata, and an explicit supplied-field set.

The adapter classifies results as `valid`, `partial`, `invalid`, `empty`, `provider_error`, or `oversized`. It requires a MediaWiki envelope, stable numeric page ID, nonempty official name/title and wikitext, safe textual content, bounded nonnegative numbers, and valid nested DTO shapes. Serialized documents are limited to 2 MiB. Script tags, event-handler payloads, and `javascript:` content are rejected. Operational failures expose safe codes rather than provider bodies or credentials.

Unknown fields remain in raw JSONB. An insufficient partial detail is retained but not normalized, so it cannot supersede a valid record. For an existing canonical row, absent, null, or empty input does not erase a populated value. Fields named in `Item.protected_fields` remain locally owned. `data_version` changes only when canonical item data changes; freshness can advance independently.

## Identity, legacy bridge, and variants

Resolution order is intentionally strict:

1. Resolve `(provider=tibiawiki, entity_type=item, external_id=pageid)` in `knowledge_external_mappings`.
2. If absent, consider only an exact normalized official name or approved alias within the Item entity type.
3. Otherwise create a permanent Item `KnowledgeEntity` UUID and stable mapping.

Fuzzy names never merge. Entity-type scoping prevents Creature/Quest collisions. A unique unmatched legacy row may be reassociated by exact normalized name; ambiguous rows fail without deletion. The migration backfills normalized names but leaves all unmatched data intact.

If an exact name already belongs to a different mapped provider page, the new page becomes a distinct variant with a page-ID-suffixed slug. Additional same-name mapped variants remain distinct. If an unmapped exact candidate makes association ambiguous, normalization reports an identity conflict instead of guessing. Database constraints prevent two provider identifiers from mapping to one provider entity and prevent multiple Item rows from pointing to one KnowledgeEntity.

## Creature drop relationship

`knowledge_creature_item_drops` is one provenance-aware fact keyed by provider and normalized Creature/Item names. Both item `dropped_by` input and creature loot input update that same record. Exact canonical names and aliases may resolve either side; fuzzy matching is forbidden. Unresolved and ambiguous references are retained with their source document IDs, input directions, exact-confidence marker, and resolution policy. Repeated input deduplicates. Conflicting same-name variants clear the guessed item link and leave the fact explicitly ambiguous. Existing embedded `Loot` rows remain available for compatibility and for chance/rarity display.

## Local reads

`GET /api/v1/items` reads canonical linked Item rows first, supports bounded pagination and safe name/category/type filters, and retains legacy Loot fallback for pre-release records not yet rebuilt. `GET /api/v1/items/{identifier}` accepts a local row ID, stable game/provider ID, slug, or exact normalized name and returns canonical fields, data version/freshness, and safe drop relationships. Missing local data returns 404 even when TibiaWiki is healthy. Neither endpoint requests provider detail data.

The Admin Data Tools derive Item options from the registered provider and adapter capabilities. They support bounded catalog enqueue, one-item detail, stored-document renormalization, parent/child jobs, attempt metrics, partial warnings, provider health, and freshness in English and Spanish. The CLI supports the same bounded operations, dry-run validation, and explicit confirmation.

## Controlled one-item smoke

Do not migrate production, enable the provider, or start a Knowledge worker until the PostgreSQL cutover is independently confirmed and Alembic is at `knowledge_item_20260724`. Then use a single known page only:

1. Enable only the registered `tibiawiki` provider and explicitly start one Knowledge worker.
2. Validate without enqueueing: `python scripts/enqueue-knowledge-job.py --provider tibiawiki --entity-type item --job-type item_detail --external-id <MEDIAWIKI_PAGE_ID> --item-name <OFFICIAL_ITEM_NAME> --dry-run`.
3. Repeat with `--confirm-enqueue-knowledge-job`, record the printed job ID, and wait for only that detail job.
4. Verify one raw document, stable mapping, Item KnowledgeEntity, linked Item row, search metadata, relationships, and a successful safe attempt.
5. Disable the provider/worker again unless broader import authority is explicit. Never use `item_catalog` for the first live smoke.

Quests, NPC entities, maps/access modeling, media downloading, unified search UI, AI, embeddings, and pgvector remain deferred.
