# Knowledge Quest Adapter — canonical overview + repair workflow

TibiaHub imports TibiaWiki Quest knowledge through the durable Knowledge worker and serves normalized Quest data exclusively from local PostgreSQL. Provider access is never part of public GET requests. Raw provider responses are retained as immutable `KnowledgeDocument` evidence and parser compatibility transforms operate on copies only.

## Canonical sources and jobs

The canonical Quest catalog is **`Category:Quest Overview Pages`**. The older mixed `Category:Quests` category is not the production discovery source. `quest_catalog` follows MediaWiki continuation tokens in bounded batches of at most 50 and creates idempotent `quest_detail` children for the overview pages.

`quest_detail` fetches one overview page by stable MediaWiki page ID. The production `TibiaWikiOverviewQuestAdapter` also schedules one bounded `quest_spoiler_detail` child for `<Quest name>/Spoiler`. A missing spoiler page is a successful no-op. When a spoiler exists, its raw response is retained separately as `quest_spoiler:<parent-page-id>` but is normalized as **auxiliary evidence for the parent Quest**, never as a second public Quest entity.

`quest_renormalize` replays the latest immutable `quest:<page-id>` document with no provider request. Focused repair tooling must resolve the registered production adapter rather than instantiating the legacy base adapter directly.

## Current TibiaWiki compatibility

Current Quest overview templates use provider-specific aliases that differ from the provider-neutral DTO:

- `lvl` → canonical `minimum_level`
- `legend` → canonical description

Those aliases are translated only in the temporary parsing copy. Retained raw evidence is unchanged.

Short Quests and Mini World Changes often keep their walkthrough in a top-level `Method` section instead of a nested `Missions` structure. The production adapter conservatively exposes the direct `Method` prose as one mission. Nested sections such as statistics are not converted into fake missions. This transform also operates only on the parsing copy.

The parser deliberately does **not** infer requirements, rewards, NPCs, or coordinates from arbitrary prose. Explicit provider fields and structured labels may become canonical facts; ambiguous prose stays unstructured until a later evidence-aware/editorial workflow can approve it.

## Identity, ownership, and provenance

Quest identity is provider + `quest` + the numeric overview-page MediaWiki ID. An existing external mapping wins, followed by one exact canonical name or approved alias. Fuzzy matching is never used. Same-name provider variants remain separate when identity evidence requires it.

Missions use a provider mission ID when available; otherwise identity is normalized title plus stable sequence inside the Quest. Spoiler evidence deliberately reuses the parent overview ID, so it can enrich the same canonical Quest without creating a `/Spoiler` entity.

TibiaWiki may own the official English name, current description/summary, mission structure, levels/status flags, explicit requirements/rewards, and related entity references. Protected fields, editorial walkthroughs, verified routes, custom map steps, community recommendations, manually corrected relationships, and future translated guides remain locally owned. Missing provider fields do not erase populated local values.

Every normalized relationship preserves source provider/document identity. Exact canonical names and approved aliases may resolve existing Quest, Item, Creature, Boss, NPC, Location, or Access entities. Ambiguous and unresolved names stay reviewable and are never guessed. No coordinates or routes are fabricated.

## Local reads

`GET /api/v1/quests/` supports local pagination and Quest filters. `GET /api/v1/quests/{identifier}` accepts a local row ID, provider page ID, slug, or exact normalized name and returns ordered missions plus safe relationships. Neither endpoint calls TibiaWiki or exposes raw wikitext/spoiler documents.

## Repair workflow

Use `scripts/repair-quest-knowledge.py` for production-safe Quest repair. It is audit-only unless an explicit repair phase and confirmation are provided.

Recommended order:

```bash
# 1. Inventory current coverage only.
python scripts/repair-quest-knowledge.py

# 2. Replay retained overview documents without network access.
python scripts/repair-quest-knowledge.py \
  --replay-existing \
  --offset 0 \
  --limit 100 \
  --wait \
  --confirm 'REPAIR TIBIAHUB QUEST KNOWLEDGE'

# Repeat with the printed next_offset until retained documents are covered.

# 3. Refresh the canonical overview catalog and detail/spoiler evidence.
python scripts/repair-quest-knowledge.py \
  --refresh-catalog \
  --batch-limit 50 \
  --wait \
  --confirm 'REPAIR TIBIAHUB QUEST KNOWLEDGE'
```

If TibiaWiki is intentionally disabled, `--enable-provider` must be supplied explicitly together with `--refresh-catalog`; the repair script never silently enables a provider.

After the durable jobs finish, run exact-only reconciliation rather than a destructive rebuild:

```bash
python scripts/reconcile-knowledge-layer.py --dry-run
python scripts/reconcile-knowledge-layer.py \
  --apply \
  --confirm APPLY-P0-KNOWLEDGE-CLOSURE
```

Then validate graph/spatial consistency and smoke the Quest/Cyclopedia APIs. This workflow never truncates canonical tables and never invents missing facts.
