# TibiaHub Product Backlog

This file tracks product work that must not be lost between implementation passes. It is intentionally separate from active PR scope and from the P0 Knowledge Layer closure report.

## NPC canonical knowledge and commerce relationships

Status: pending
Priority: high after the current Cyclopedia/navigation work

TibiaHub must maintain NPCs as first-class canonical knowledge in PostgreSQL, with their useful TibiaWiki data and relationships normalized rather than treating NPC names as loose text.

Required outcomes:

- NPCs can be found and explained by the TibiaHub AI assistant using local canonical knowledge.
- Item Detail can resolve who sells an item and who buys it, with links to the canonical NPC detail instead of plain text when the relationship is known.
- NPC Detail must expose the information needed to find/use the NPC: location, canonical spatial relationship when available, buying/selling inventory, access requirements, quest requirements, notes and other supported facts.
- Item/NPC relationships must distinguish at least `sold_by` / seller and `bought_by` / buyer semantics. Unknown or unresolved relationships remain explicit; do not invent matches.
- Cyclopedia > Loot keeps the existing item-category filter intact and adds a separate optional NPC browser/filter experience.
- The NPC selector should behave similarly to the expandable Creature category browser: show the NPC list with local sprite/GIF/media where available; selecting an NPC filters Loot by that NPC's commerce relationship.
- Selecting/opening an NPC must also allow navigation to the NPC Detail page.
- Consider separate Buyer and Seller modes (or equivalent relationship toggle) so the same NPC can filter items it buys vs. items it sells without overloading the existing Loot category facet.
- Runtime reads remain PostgreSQL-only. Provider synchronization/reconciliation belongs to admin/jobs.

Before UI implementation, audit current NPC canonical coverage, raw TibiaWiki documents, external IDs, media coverage, locations, quest/access relations and existing item trade fields so historical data can be reused rather than duplicated.

## Full localization and automatic content translation

Status: pending
Priority: high product/platform work

Goal: the entire user-facing system should support localization, including dynamic knowledge content, not only static interface labels.

### Static UI

- Complete i18next coverage for every user-facing frontend string.
- Remove remaining hard-coded English/Spanish copy from components.
- Start with English and Spanish as fully supported languages; architecture should allow additional locales later.

### Canonical/dynamic knowledge content

Automatic translation is feasible, but translated prose must NOT overwrite canonical provider data or immutable `KnowledgeDocument` raw content.

Recommended model:

- Keep canonical source facts/content in their provider-derived form.
- Store translations separately, keyed by canonical entity, field, locale and source-content hash/version.
- Record translation provenance such as provider/model/version, generated timestamp and review/status.
- When source content changes, mark the corresponding translation stale and enqueue retranslation.
- Generate translations asynchronously through jobs/admin workflows, never by calling an external translation/LLM provider from a public runtime GET.
- Public runtime serves the requested locale from PostgreSQL and falls back to canonical/original content when a translation is missing.
- Maintain a Tibia terminology glossary/do-not-translate policy. Proper names such as creature names, item names, NPC names, quest names, cities and game-specific terms normally remain canonical unless a deliberate localized display name exists.
- Allow reviewed/manual translations to be protected from automatic overwrite.
- Cache/render translated content independently from source ingestion while preserving the raw-data/provenance model.

A first implementation should define the translation schema + stale/version semantics, translate a small representative domain, then perform a controlled backfill rather than translating the whole database in one pass.

## Current product follow-ups

- Finish and validate Cyclopedia shell/navigation/cache work from PR #59.
- Footer with professional product/about/privacy/cookies/legal links.
- Cookie/privacy consent with persisted preferences and configurable optional categories.
- Rashid/boosted/current-world product experience after the shell work is stable.
- Google/Discord SSO as a separate authentication/security project rather than bundling it into UI polish.
- Continue media-coverage inventory and eliminate repeated missing-media requests through canonical/local media reconciliation.

## Completed foundations relevant to this backlog

- P0 Knowledge Layer reconciliation/closure is merged.
- Quest Library and Quest Detail product polish is merged.
- Cyclopedia Loot browser exists with canonical item category facets.
- Canonical NPC and item-related entity support exists in parts of the current detail model, but full NPC catalog/commerce coverage and NPC-based Loot filtering are not yet complete.
