# TibiaHub content localization

## Goal

TibiaHub keeps provider data and canonical identities independent from presentation language. Long-form knowledge content can be authored or ingested in English, Spanish, Portuguese, or another supported language and rendered in the language requested by the user.

This is content localization, not UI-string localization. Existing frontend i18n continues to own buttons, labels, navigation, and other interface copy.

## Core rules

1. Provider/canonical rows remain the source of truth; machine translation never rewrites provider evidence.
2. `knowledge_localizations` stores one localized field value per resource, field path, and language.
3. Each localization retains a source text snapshot and source hash for review/staleness detection; immutable provider documents remain the underlying evidence.
4. Machine-generated content starts as `generated`.
5. Reviewers can promote content to `reviewed` or `approved`; approved content is locked.
6. Approved/locked translations are never silently overwritten. A changed source updates the source snapshot/hash and marks the translation `stale` for human review.
7. Tibia proper nouns are protected before translation and restored afterward.
8. Language selection follows BCP-47-style fallback. Example: `es-MX -> es -> en` and `pt-BR -> pt -> en`.
9. Translation providers are adapters. TibiaHub is not coupled to OpenAI, DeepL, Google, or a self-hosted engine.
10. Translation provider calls happen only in the isolated localization worker. Canonical sync transactions only enqueue durable work.
11. Public reads never wait on a translation provider. `stale` and `failed` variants are excluded from localized reads and fall back to current canonical/source text.

## Implemented translatable fields

Automatic planning currently covers prose-oriented fields:

- Creature: `description`, `behavior`, `strategy`, `notes`
- Item: `description`, `notes`
- Quest: `description`, `summary`, mission descriptions and textual objectives
- NPC: `title`, `occupation`, `location_text`, `description`
- Location / area / town: `description`, `access_notes`
- Hunt zone: `description`, `access_notes`, `vocation_text`

The existing-content backfill covers the persisted fields available on current canonical/bridge models, including hunt-zone `tips`.

Names, slugs, IDs, coordinates, image URLs, numeric stats and relationship identifiers are not automatically translated. Canonical names, aliases and discovered entity references are instead used as protected terminology.

## Persistence and lifecycle

### `knowledge_localizations`

One row represents one language variant of one field. It stores:

- stable resource identity and optional `knowledge_entity` UUID
- target language and localized text
- detected/declared source language
- latest source text snapshot and SHA-256 source hash
- origin (`provider`, `machine`, `human`)
- lifecycle (`generated`, `reviewed`, `approved`, `stale`, `failed`)
- provider/model provenance
- reviewer/approver identity and timestamps
- lock state

### `localization_jobs`

Translation work is durable and idempotent. The key includes resource, field, source language, target language and source hash. The queue supports:

- `pending`, `processing`, `retry`, `succeeded`, `failed`, `cancelled`
- worker leases and recovery after interruption
- bounded exponential retry for transient provider failures
- safe failure categories without persisting external-provider secrets/errors
- source snapshots so provider work is detached from later canonical mutations

### Worker heartbeat

`localization_worker_heartbeats` exposes worker state, last seen time, last successful translation and safe last failure category for operations diagnostics.

## Sync integration

TibiaWiki canonical adapters already converge in `KnowledgeNormalizationService`. After a supported entity is successfully `created` or `updated`, the localization planner may enqueue target-language jobs.

This path is deliberately non-blocking with respect to the translation provider:

1. fetch/validate provider document
2. normalize and persist canonical content
3. enqueue localization jobs in the database when enabled
4. commit canonical sync normally
5. localization worker later calls the configured provider

Provider outage, timeout or malformed translation therefore cannot turn a successful canonical sync into a failed sync.

Automatic enqueueing is controlled independently from the feature itself.

## Existing-content backfill

The admin backfill can queue existing canonical data without re-running the external Tibia sync. It supports:

- creatures
- items
- quests and missions
- NPCs
- locations
- hunt zones

Backfill uses an integer cursor (`after_id`), batches of at most 500 records and the same queue idempotency rules. Repeating the same batch does not duplicate jobs and reports only newly-created jobs in `queued`.

Start with small batches so terminology and output quality can be reviewed before expanding coverage.

## Reviewer workflow

The admin localization API and Data Tools localization panel provide:

- queue/worker diagnostics
- generated, reviewed, approved, stale and failed filters
- target-language/resource filters
- source snapshot and translation side by side
- human edit + mark reviewed
- approve + lock
- explicit unlock for future regeneration
- small paginated/idempotent backfill batches

Review/approval/backfill actions are recorded through `WorkspaceAudit`.

A future author-in-any-language phase will allow a reviewer-created Spanish/Portuguese/English value to become an explicit source variant and enqueue missing languages. The current branch already supports provider-side source-language detection and machine translation from `auto`, but the complete authoring workflow is not yet connected to all content editors.

## Read fallback

`ContentLocalizationService.resolve_text` implements the backend resolution primitive. For a request in `es-MX`:

1. current `es-MX` variant (`approved`, `reviewed`, or `generated`)
2. current `es` variant
3. canonical/source language when encountered in fallback
4. canonical/source text

`stale` and `failed` values are never returned as current public localized content.

The remaining public-read phase is to apply this resolver in Cyclopedia projection/detail endpoints and expose selected language/status in a backward-compatible response shape.

## Translation provider

The branch includes a provider-neutral protocol and an initial OpenAI Responses API adapter because TibiaHub already uses `httpx` and has an `OPENAI_API_KEY` secret path. No new Python package is required for this adapter.

The OpenAI adapter asks the provider to return translated text plus detected source language, allowing an upstream Portuguese document to be ingested with `source_language=auto` and subsequently recorded as `pt-BR`/`pt` when detected.

A DeepL, Google Cloud or self-hosted adapter can be added without changing persistence or reviewer workflows. Provider-specific glossaries should be treated as an optimization; TibiaHub's protected-term layer remains authoritative for game names.

## Runtime switches

All switches default to safe/off values:

```env
LOCALIZATION_ENABLED=false
LOCALIZATION_AUTO_ENQUEUE=false
LOCALIZATION_PROVIDER=openai
LOCALIZATION_MODEL=gpt-5-mini
LOCALIZATION_DEFAULT_LANGUAGE=en
LOCALIZATION_TARGET_LANGUAGES=es,pt-BR
LOCALIZATION_WORKER_ENABLED=false
```

The switches have distinct purposes:

- `LOCALIZATION_ENABLED`: enables localization storage/admin queue operations.
- `LOCALIZATION_AUTO_ENQUEUE`: allows canonical sync to create jobs automatically.
- `LOCALIZATION_WORKER_ENABLED`: permits the separate worker to call the translation provider.

`OPENAI_API_KEY` is required only when the OpenAI localization worker is enabled. This allows schema/API/reviewer deployment and queue inspection without enabling external API consumption.

## Staged VPS rollout

Do not apply the migration to the live database until CI/manual validation is complete and a database backup exists.

Recommended stages:

### Stage A - deploy schema/code inert

```env
LOCALIZATION_ENABLED=false
LOCALIZATION_AUTO_ENQUEUE=false
LOCALIZATION_WORKER_ENABLED=false
```

Apply the migration and verify API/worker process definitions. No translation jobs or provider calls can occur.

### Stage B - enable admin localization only

```env
LOCALIZATION_ENABLED=true
LOCALIZATION_AUTO_ENQUEUE=false
LOCALIZATION_WORKER_ENABLED=false
```

Inspect diagnostics and queue a very small manual/backfill batch. Jobs remain durable and unprocessed; no provider API key is required yet.

### Stage C - execute a controlled sample

Add the provider credential through `/forge/tibiahub-secrets/runtime.env`, then enable:

```env
LOCALIZATION_WORKER_ENABLED=true
```

Process/review a small sample before increasing coverage.

### Stage D - controlled existing-content backfill

Queue 10-20 records first, inspect Spanish/Portuguese terminology and reviewer UX, then advance the cursor in measured batches.

### Stage E - future sync automation

Only after translation quality and operations are accepted:

```env
LOCALIZATION_AUTO_ENQUEUE=true
```

New/changed canonical TibiaWiki content then automatically schedules target-language variants while remaining independent from provider availability.

## Remaining phases

1. **Public Cyclopedia localized reads**: accept `lang`/`Accept-Language`, apply stored localizations in projections and return locale/status metadata without breaking existing clients.
2. **Author in any language**: make reviewer-authored prose an explicit source-language variant and enqueue other configured languages.
3. **Coverage reporting**: percentages and stale/generated/approved coverage by entity family and language.
4. **Bulk review/regeneration controls** with conservative limits and cost visibility.
5. **Additional providers** if quality/cost warrants them.
