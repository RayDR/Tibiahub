# Quest editorial foundation

This note records the audited boundary for future Quest editorial, media, and community work. It is a contract, not a claim that those capabilities currently exist.

## Current audit

- Canonical Quest facts and normalized missions come from the provider-backed PostgreSQL model.
- `KnowledgeDocument.raw_json` is immutable ingestion evidence and must not become an editable guide body.
- `protected_fields` controls provider overwrite behavior; it is not an author, reviewer, approval, or publication marker.
- The current Quest schema has no editorial version, author/reviewer lifecycle, Quest attachment/video binding, or Quest comment/moderation model.
- Generic media rows are image-cache records for other entity domains and are not evidence that a Quest owns a gallery or video.
- Leadership comments are workflow-specific and must not be repurposed as public Quest comments.

The frontend therefore renders no editorial badge, video, or comments without an explicit future API contract. `QuestEditorialMarker` is intentionally null when editorial state is absent.

## Versioned editorial overlay

Add a separate overlay keyed by canonical Quest identity and locale. Each immutable revision should contain the rendered body plus `version`, `state`, `author_id`, optional `reviewer_id`, creation/review/publication timestamps, provenance, source-document hashes, and a content hash. The lifecycle is:

`draft → review → approved → published`

Only a published revision is public. Approval and publication are explicit audited transitions, not booleans inferred from content presence. A new edit creates a new revision; it never mutates the published revision or raw provider document.

Provider resynchronization updates canonical facts and creates new immutable `KnowledgeDocument` evidence. It must not overwrite editorial revisions. Source hashes let the system mark an overlay stale for human review while keeping the last published revision available. Protected/manual corrections and translations retain their existing ownership boundaries.

## Media and video contract

Future Quest media needs an explicit Quest/revision attachment table with media kind, canonical ownership, local asset reference, source/provenance, moderation state, ordering, caption/alt text, and timestamps. Video support should accept only an allowlisted provider plus validated canonical video identifier (or a locally managed asset), use a privacy-conscious player, and never render arbitrary HTML or provider URLs from raw prose. Public reads remain PostgreSQL-only.

## Comments contract

Quest comments require a reusable public discussion model with canonical entity/revision scope, author identity, edit history, moderation state/reason, reports, rate limits, permissions, and deletion/audit semantics. Implement that platform independently; do not couple Quest pages to leadership recruitment comments.

## Rich links

`RichEntityLink` receives a structured, already-resolved canonical target. Callers may create it only from exact resolved relationships or canonical IDs/slugs returned by the API. It must never scan prose or guess a destination by fuzzy name matching.
