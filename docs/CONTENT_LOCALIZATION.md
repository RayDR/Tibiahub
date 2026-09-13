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
6. Reviewer-authored prose is stored as a protected human locale variant and can seed translations to other languages without rewriting canonical provider content.
7. Approved/locked translations are never silently overwritten. A changed source updates the source snapshot/hash and marks the translation `stale` for human review.
8. Tibia proper nouns are protected before translation and restored afterward.
9. Language selection follows BCP-47-style fallback. Example: `es-MX -> es -> en` and `pt-BR -> pt -> en`.
10. Translation providers are adapters. TibiaHub is not coupled to OpenAI, DeepL, Google, or a self-hosted engine.
11. Translation provider calls happen outside canonical sync transactions through a dedicated localization execution lane. Canonical sync only enqueues durable work.
12. Public reads never call the translation provider. They overlay already-persisted variants and fail open to canonical/source content.

## Implemented translatable fields

Automatic planning currently covers prose-oriented fields:

- Creature: `description`, `behavior`, `strategy`, `notes`
- Item: `description`, `notes`
- Quest: `description`, `summary`, mission descriptions and textual objectives
- NPC: `title`, `occupation`, `description`
- Location / area / town: `description`, `access_notes`
- Hunt zone: `description`, with canonical `access_notes` projected to public `access.notes`

The existing-content backfill also covers currently persisted hunt-zone `tips`.

Names, slugs, IDs, coordinates, image URLs, numeric stats and relationship identifiers are not automatically translated. Canonical names, aliases and discovered entity references are instead used as protected terminology.

## Persistence and lifecycle

### `knowledge_localizations`

One row represents one language variant of one field. It stores stable resource identity, optional `knowledge_entity` UUID, language and text, detected/declared source language, latest source snapshot/hash, origin (`provider`, `machine`, `human`), lifecycle (`generated`, `reviewed`, `approved`, `stale`, `failed`), provider/model provenance, reviewer/approver audit metadata and lock state.

Human-authored source variants use `origin=human`, begin as `reviewed`, and are locked so automatic generation cannot silently replace them.

### `localization_jobs`

Translation work is durable and idempotent. The key includes resource, field, source language, target language and source hash. The queue supports `pending`, `processing`, `retry`, `succeeded`, `failed`, `cancelled`, leases, interruption recovery, bounded retry/backoff, safe failure categories and immutable source snapshots.

### Worker heartbeat

`localization_worker_heartbeats` exposes localization-lane state, last-seen time, last successful translation and safe last failure category for operations diagnostics.

## Sync integration

Canonical adapters converge in `KnowledgeNormalizationService`. After a supported entity is successfully `created` or `updated`, the provider-neutral localization planner may enqueue target-language jobs.

Planning runs in its own nested transaction/savepoint. A localization queue/planning failure is logged as a warning/metric and cannot roll back the already-normalized canonical entity.

The flow is:

1. fetch and validate provider document
2. normalize and persist canonical content
3. best-effort enqueue localization jobs when enabled
4. commit canonical sync normally
5. localization lane later calls the configured provider using independent sessions/leases

Provider outage, timeout or malformed translation therefore cannot turn a successful canonical sync into a failed canonical sync.

Source language may be declared by a provider or set to `auto`. This permits future English or Portuguese providers without changing the localization schema or workflow.

## Existing-content backfill

The admin backfill can queue existing canonical data without re-running external Tibia synchronization. It supports creatures, items, quests/missions, NPCs, locations and hunt zones.

Backfill uses an integer cursor (`after_id`), batches of at most 500 records and queue idempotency. It inspects provider/parser/raw metadata for per-record `language`/`source_language`, so a mixed English/Portuguese dataset does not need one global source-language assumption.

## Reviewer workflow

The admin localization API and Data Tools localization panel provide:

- queue/lane diagnostics
- generated, reviewed, approved, stale and failed filters
- target-language/resource filters
- source snapshot and translation side by side
- human edit + mark reviewed
- approve + lock
- explicit unlock for future regeneration
- paginated/idempotent existing-content backfill
- an **Author in any language** workflow where a reviewer supplies resource identity, field path, source language, target locales, protected Tibia terms and prose

Reviewer-authored source text is persisted before target jobs are created. For example, Spanish prose can remain the protected Spanish variant while durable jobs generate English and `pt-BR` variants.

Review/approval/unlock/backfill/manual-authoring actions are recorded through `WorkspaceAudit`.

## Public localized reads

`PublicLocalizationMiddleware` applies persisted variants to public detail JSON for:

- creatures
- items
- quests
- NPCs
- locations
- hunt zones

It never calls OpenAI or any translation provider. It only reads `knowledge_localizations`; an exception falls back to the original API response.

Language precedence is:

1. explicit `?lang=` query parameter
2. `tibiahub_lang` cookie written by TibiaHub's language selector
3. `Accept-Language`
4. configured default language

The middleware adds `Vary: Accept-Language` and diagnostic response headers. The frontend clears its in-memory knowledge cache and reloads current content after an explicit language change, preventing a response cached in one language from being reused after switching languages.

`stale` and `failed` rows are excluded from public projection. Locale fallback still uses stored current variants (`generated`, `reviewed`, `approved`) before canonical/source content.

## Translation provider and existing OpenAI credential

The branch includes a provider-neutral protocol and an OpenAI Responses API adapter because TibiaHub already uses `httpx` and already has `OPENAI_API_KEY` in the external runtime secret file.

**There is deliberately no `LOCALIZATION_OPENAI_API_KEY` or second API key.** The localization factory reads the existing `settings.OPENAI_API_KEY`. Production receives it through the same `/forge/tibiahub-secrets/runtime.env` already used by TibiaHub.

The key is never copied into `ecosystem.config.js`, frontend/Vite variables, database rows, queue payloads or logs.

The OpenAI adapter returns translated text plus detected source language, allowing `source_language=auto` to recognize Portuguese/English source material. A future DeepL, Google Cloud or self-hosted adapter can be added without changing persistence or reviewer workflows.

## Runtime switches

All localization switches default off:

```env
LOCALIZATION_ENABLED=false
LOCALIZATION_AUTO_ENQUEUE=false
LOCALIZATION_PROVIDER=openai
LOCALIZATION_MODEL=gpt-5-mini
LOCALIZATION_DEFAULT_LANGUAGE=en
LOCALIZATION_TARGET_LANGUAGES=en,es,pt-BR
LOCALIZATION_WORKER_ENABLED=false
```

The switches have distinct purposes:

- `LOCALIZATION_ENABLED`: enables localization storage/admin/public projection behavior.
- `LOCALIZATION_AUTO_ENQUEUE`: lets successful canonical normalization schedule translations automatically.
- `LOCALIZATION_WORKER_ENABLED`: lets the localization execution lane make provider calls.

When the OpenAI lane is enabled, configuration validates that the existing `OPENAI_API_KEY` is present.

## Runtime topology

No additional PM2 service is required. The existing managed `tibiahub-sync-worker` starts a dedicated localization thread only when both `LOCALIZATION_ENABLED=true` and `LOCALIZATION_WORKER_ENABLED=true`.

The localization lane uses its own queue claims, database sessions, leases and heartbeat. Provider exceptions are contained in that lane and cannot terminate or roll back sync work. This preserves the existing deploy/rollback service contract while keeping provider work outside canonical sync transactions.

The standalone `app.workers.localization_worker` entry point remains available for focused development/testing, but normal VPS operation uses the managed sync-worker lane.

## Activation strategy

Code/schema may be deployed inert with all switches false. Activation can then be controlled through `/forge/tibiahub-secrets/runtime.env` without introducing a second OpenAI secret.

A normal initial runtime configuration for the feature is:

```env
LOCALIZATION_ENABLED=true
LOCALIZATION_AUTO_ENQUEUE=false
LOCALIZATION_WORKER_ENABLED=true
```

This permits reviewer/backfill/manual translation while preventing every future sync from automatically generating work. After quality/cost are accepted, `LOCALIZATION_AUTO_ENQUEUE=true` enables continuous translation scheduling for newly changed canonical content.

## Validation policy

This feature is validated as one complete gate, not as a sequence of partial user validations. Before asking for VPS validation, the branch must have:

- complete backend compile/tests for localization integration
- frontend typecheck/lint/build at the repository gate
- one Alembic head and a valid migration path
- canonical-sync isolation tests/contracts
- persisted source-language and public-projection tests
- reviewer authoring/review/approval/stale lifecycle coverage
- OpenAI credential reuse verified without exposing the key
- branch synchronized with current `develop`

Only after those checks are complete should the VPS validation exercise migration, worker/lane startup, one real OpenAI translation, locale switching/public reads, review/lock/stale behavior and sync safety as a single end-to-end acceptance run.
