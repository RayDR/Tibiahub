# Creature Semantic and Media Hardening

Date: 2026-09-14

## Scope

This checkpoint closes the first Creature data-quality phase for TibiaHub.

The work covered:

- Creature semantic normalization
- Behavior / strategy separation
- Notes and description semantics
- Explicit-empty vs blank provider fields
- Numeric unknown-value cleanup
- Local strategy transclusion resolution
- Creature media evidence
- MediaAsset repair and reconciliation
- Regression coverage and idempotency gates

## Semantic normalization

Visible canonical creatures:

- 2,192 visible
- 2,192 mapped
- 2,192 with TibiaWiki external IDs

The normalization contract now distinguishes:

1. Complete provider documents
2. Opaque/global partial documents
3. Field-aware partial documents
4. Explicit semantic-empty source values
5. Blank source values
6. Absent source fields

### Behavior and strategy

TibiaWiki semantics are preserved:

- `behaviour` / `behavior`: what the creature does
- `strategy`: player tactics for fighting the creature

The historical parser behavior:

    behavior = strategy or behaviour

is no longer used.

The known historical strategy-to-behavior fingerprint can be repaired without
blindly deleting useful canonical prose.

### Explicit empty values

Provider values such as:

- Unknown
- None
- ?
- N/A

are recognized separately from merely blank parameters.

Explicit semantic-empty provider evidence may clear stale canonical values.

Blank provider fields may only clear semantic placeholders and do not erase
useful existing prose.

### Numeric unknown values

Historical zero sentinels caused by unknown provider values are cleared only
when current provider evidence explicitly says the field is unknown.

Legitimate source zero values remain valid.

Fields covered include:

- hitpoints
- experience
- armor
- speed
- max damage

## Strategy transclusions

Local TibiaWiki `#lsth` strategy references are supported using already stored
KnowledgeDocuments.

No provider request is performed during normalization.

The resolver requires an exact stored page and exact section heading.

The 11 known Creature strategy transclusions were resolved successfully.

## Semantic idempotency gate

Final stored-document dry run:

- processed: 2,192
- creatures with changes: 0
- creatures unchanged: 2,192
- missing documents: 0
- errors: 0
- loot count changes: 0
- spawn count changes: 0

All tracked canonical fields reported zero changes.

## Creature media

The previous media implementation inferred:

    actualname -> actualname.gif

This is retained only as a compatibility fallback and is not authoritative
provider evidence.

Creature detail ingestion now requests:

    MediaWiki parse prop=wikitext|images

When available, the authoritative image is selected only when a referenced
MediaWiki file has a filename stem exactly matching the page title.

Examples:

    Blooming Tower (Dark)
      -> File:Blooming Tower (Dark).gif

    Monk (Creature)
      -> File:Monk (Creature).gif

Related images such as Soul Core images, maps, icons and anniversary artwork
are rejected by the exact matcher.

## Media authority

Media availability and media authority are separate concepts.

A synthetic name-derived Special:FilePath URL:

- remains available as compatibility fallback
- does not mark `image_reference` as provided
- cannot overwrite canonical media during normalization
- does not make the entire Creature detail document partial

Only `page_images_exact` evidence is authoritative.

## Media repair

36 previously missing Creature media records were audited against MediaWiki.

Results:

- exact image references: 36
- successful downloads: 36
- failed downloads: 0
- distinct file references: 36
- distinct resolved URLs: 36
- distinct content hashes: 36
- duplicate content hashes: 0

Persistence results:

- existing missing MediaAssets repaired: 35
- new MediaAssets created: 1
- Creature links updated: 36

One legacy source URL casing mismatch for Devoted Radiant Paragon was also
normalized after proving the canonical and legacy URLs produced identical
content and SHA-256.

## Final Creature media gate

Global visible Creature media:

- visible: 2,192
- with image_asset_id: 2,192
- without image_asset_id: 0
- broken MediaAsset foreign keys: 0
- cached assets: 2,192
- cached files present: 2,192
- non-cached linked assets: 0
- asset key mismatches: 0
- source URL mismatches: 0
- old unsupported-content error residue: 0

Result:

    PASS

## Regression suite

Creature adapter regression suite:

    37 passed

## Important database note

Some repairs in this phase were persistent data corrections in the current
TibiaHub database. Those row-level mutations are not represented by Git history
alone.

The source changes in this checkpoint prevent the identified semantic and media
defects from being reintroduced by future synchronization.

## Next phases

Recommended order:

1. Creature detail UI semantic separation
   - Description / Overview
   - Behavior
   - Strategy
   - Notes

2. Investigate the 807 Creature pages whose loot is represented through
   Loot Table-only source structures before modifying loot parsing.

3. Audit Creature spatial/location relationships and exact coordinates.

4. Extend the same evidence-driven quality gates to the remaining Cyclopedia
   entity types.
