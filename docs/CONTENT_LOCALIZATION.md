# TibiaHub content localization

## Goal

TibiaHub keeps provider data and canonical identities independent from presentation language. Long-form knowledge content can be authored or ingested in English, Spanish, Portuguese, or another supported language and rendered in the language requested by the user.

This is content localization, not UI-string localization. Existing frontend i18n continues to own buttons, labels, navigation, and other interface copy.

## Core rules

1. Provider/canonical rows remain the source of truth; machine translation never rewrites provider evidence.
2. `knowledge_localizations` stores one localized field value per resource, field path, and language.
3. A source hash identifies whether the canonical text changed after a translation was created.
4. Machine-generated content starts as `generated`.
5. Reviewers can promote content to `reviewed` or `approved` and lock it.
6. Approved/locked translations are never silently overwritten. A changed source marks them `stale` for human review.
7. Tibia proper nouns are protected before translation and restored afterward.
8. Language selection follows BCP-47 style fallback. Example: `es-MX -> es -> en` and `pt-BR -> pt -> en`.
9. Translation providers are adapters. TibiaHub is not coupled to OpenAI, DeepL, Google, or a self-hosted engine.
10. Translation happens asynchronously when connected to sync/reviewer workflows; public reads never wait on a translation provider.

## Initial translatable fields

The first integration should focus on prose rather than identifiers:

- Creature: `description`, `behavior`, `strategy`, `notes`
- NPC: `description`
- Location: `description`, `access_notes`
- Quest: `description`, `summary`, mission descriptions/objectives where textual
- Hunt zone: descriptions, access notes, strategy/tips fields where present
- Items: descriptions/notes where present

Names, slugs, IDs, coordinates, image URLs, numeric stats, vocation names used as identifiers, and relationship keys are not automatically translated.

## Reviewer workflow

A reviewer may write a field in their preferred language. That language becomes the source language for that edit. TibiaHub stores the human-authored localized value and enqueues missing target languages. A reviewer can then inspect machine-generated variants, edit them, approve them, or leave them generated.

Recommended states:

- `generated`: provider-generated translation, not reviewed
- `reviewed`: human checked/edited
- `approved`: publish-preferred and protected
- `stale`: canonical source changed after review/approval
- `failed`: translation provider failed; canonical source remains usable

## Read fallback

For a request in `es-MX`:

1. approved/reviewed `es-MX`
2. generated `es-MX`
3. approved/reviewed `es`
4. generated `es`
5. canonical English/source text

The API should expose the selected language and localization status so the frontend can optionally show that a translation is machine-generated.

## Translation provider

The branch includes a provider-neutral protocol and an initial OpenAI Responses API adapter because TibiaHub already uses `httpx` and has an `OPENAI_API_KEY` secret path. No new Python package is required for this adapter.

A DeepL or Google Cloud adapter can be added without changing persistence or reviewer workflows. Provider-specific glossaries should be treated as an optimization; TibiaHub's own protected-term layer remains authoritative for game names.

## Integration phases

### Phase 1 - foundation (this branch)

- durable localization model and migration
- locale normalization/fallback helpers
- Tibia term masking/restoration
- provider-neutral translation contract
- OpenAI adapter
- unit tests for locale fallback and protected terms

### Phase 2 - sync integration

After canonical normalization succeeds, compare source hashes for translatable fields and enqueue missing/stale translations. Translation failure must never fail the canonical sync job.

### Phase 3 - localized reads

Add `lang` / `Accept-Language` resolution to Cyclopedia read endpoints and apply localizations in projection services. Keep response shape backward-compatible.

### Phase 4 - reviewer tools

Add admin endpoints and UI for generated/stale translations, side-by-side source/target editing, approve/lock actions, bulk regeneration, and language coverage metrics.

### Phase 5 - author-in-any-language

Reviewer-created prose is stored with its explicit source language, then missing variants are queued automatically. Machine translations must never overwrite another human-authored variant.

## VPS rollout safety

Do not apply this migration to the live database until the branch tests pass and a database backup exists. The foundation does not call a translation API automatically, so merging/applying the migration alone cannot create translation usage charges.
