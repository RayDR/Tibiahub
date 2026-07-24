# Knowledge Quest Adapter — Stage 2A-5

Stage 2A-5 imports TibiaWiki quest pages through the durable Knowledge worker and serves normalized Quest data exclusively from PostgreSQL. The provider remains disabled by default, no job is enqueued at startup, and catalog execution always requires an explicit bounded batch and confirmation.

## Source and jobs

The existing TibiaWiki MediaWiki API remains the source. `Category:Quests` supplies a continuation-token catalog; `action=parse` supplies stable page IDs, wikitext, and links for details. `quest_catalog` stores each catalog response and creates at most 50 idempotent detail children. A group page can create at most 50 bounded child-page jobs. `quest_detail` imports one page, and `quest_renormalize` replays the latest immutable `quest:<page-id>` document without network access. There is no claimed incremental feed.

Raw response shapes remain inside the adapter. Known infobox and mission sections become a provider-neutral DTO, while unknown envelope fields remain in `knowledge_documents.raw_json` and safely stripped, unparsed section text remains in parser metadata. Executable markup is rejected. Partial mission parses are stored but never normalized over valid local data.

## Identity and ownership

Quest identity is provider + `quest` + numeric MediaWiki page ID. An existing external mapping wins, followed by an exact normalized canonical name or approved alias. Fuzzy matching is never used. Same-name pages with different provider IDs receive distinct UUIDs and slugs. Missions use a provider mission ID when available; otherwise their identity is normalized title plus stable sequence within the quest.

TibiaWiki may own the official English name, current description and summary, mission structure, level and status flags, explicit requirements, rewards, and related entity references. Protected fields, editorial walkthroughs, verified routes, custom map steps, community recommendations, manually corrected relationships, and future translated guides remain locally owned. Missing or empty provider fields do not erase populated values, and protected relationship records are not overwritten. Canonical Quest `data_version` changes only when Quest or Mission data changes.

## Relationships and access

One provenance-bearing `knowledge_quest_relations` record stores each directed fact. Exact names and approved aliases can resolve existing Quest, Item, Creature, Boss, or Access entities; ambiguous and unresolved names remain reviewable and are never guessed. NPC and Location references remain unresolved named records until their future adapters exist. No coordinates or routes are fabricated.

Access unlocks create or reuse an `access` KnowledgeEntity and a minimal `knowledge_accesses` bridge containing an access code, name, description, unlocking Quest, requirements, destination name, and provider metadata. It deliberately contains no map geometry.

## Local reads and operations

`GET /api/v1/quests/` supports pagination plus category, level, premium, repeatable, and group filters. `GET /api/v1/quests/{identifier}` accepts a local row ID, provider page ID, slug, or exact normalized name and returns ordered missions and safe relationships. Neither endpoint calls TibiaWiki or exposes raw wikitext.

The admin Knowledge Operations page exposes only registered quest catalog/detail/renormalize jobs, including parent/child state and Quest attempt metrics. The safe CLI supports `--quest-name`; catalog jobs require `--confirm-catalog-sync` and an explicit `--batch-limit`.

## Production gate and one-page smoke

Do not apply the migration, enable TibiaWiki, or start the production Knowledge worker until the PostgreSQL cutover is independently confirmed. After that gate, enable the registered provider deliberately and enqueue only one known page first:

```bash
backend/venv/bin/python scripts/enqueue-knowledge-job.py \
  --provider tibiawiki \
  --entity-type quest \
  --job-type quest_detail \
  --external-id 700 \
  --quest-name "Explorer Society Quest" \
  --confirm-enqueue-knowledge-job
```

Verify the job, immutable document, mapping, Quest, ordered missions, relationships, and local API before considering a separately confirmed bounded catalog batch. NPC ingestion, Maps/PostGIS, media downloads, unified search, embeddings, and AI remain deferred.
