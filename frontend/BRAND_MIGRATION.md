# TibiaHub Brand Migration

This file turns `BRAND_SYSTEM.md` into an incremental implementation plan. It exists so visual consistency work is not reduced to documentation-only output.

## Phase 1 — Foundation

Status: in progress on `design/tibiahub-brand-foundation-v1`.

- [x] Establish `BRAND_SYSTEM.md` as product-level visual authority.
- [x] Separate canonical TibiaHub identity from user-selectable themes.
- [x] Define typography, shape, motion, icon, game-media, Cyclopedia, map, and shell rules.
- [x] Add automated brand validation.
- [x] Make `DESIGN_SYSTEM.md` reference the higher-level brand contract.
- [ ] Add `check:brand-system` to package scripts / CI entry points.

## Phase 2 — Canonical identity assets

- [ ] Rebuild the official logo asset set from one approved source.
- [ ] Produce wordmark, compact mark, favicon, app icon, monochrome mark, and safe-area variants.
- [ ] Define canonical OG/social templates.
- [ ] Define TibiaHub background/pattern library.
- [ ] Document minimum logo size, padding, and misuse examples.

No generated asset becomes canonical until its exact role is documented in `BRAND_SYSTEM.md`.

## Phase 3 — Icon system migration

- [ ] Keep Lucide as the sole generic interface icon source.
- [ ] Replace Font Awesome Cyclopedia icons with TibiaHub-owned domain SVG components.
- [ ] Expand `components/icons` for creatures, bosses, loot, quests, zones, NPCs, maps, guild concepts, and other domain concepts only where generic UI icons are insufficient.
- [ ] Remove Font Awesome packages once no application imports remain.
- [ ] Tighten `check-brand-system.mjs` by deleting migration allowlists.

## Phase 4 — Product component normalization

Audit shared visual patterns against the brand system before page-by-page redesign.

Priority components:

- [ ] Navigation / mobile navigation.
- [ ] PageHeader and section headers.
- [ ] Search/filter toolbars.
- [ ] Tabs and segmented navigation.
- [ ] Entity/result cards.
- [ ] Stat blocks and badges.
- [ ] Empty/loading/error states.
- [ ] Dialogs/dropdowns/tooltips.
- [ ] Data tables and responsive card-list equivalents.

New primitives are added only when at least two product surfaces need the same visual behavior or when the primitive represents a stable product-level contract.

## Phase 5 — Cyclopedia reference implementation

Cyclopedia becomes the first complete reference surface for the brand system.

- [ ] Creatures.
- [ ] Bosses.
- [ ] Loot/items.
- [ ] Quests.
- [ ] Hunt zones.
- [ ] NPCs.
- [ ] Entity detail pages.
- [ ] Sprite/GIF sizing and fallback rules.
- [ ] Search/filter/pagination/infinite-loading patterns.
- [ ] Coordinates and map integrations.

NPC compact cards should be treated as an explicit reference for small sprite-driven entities: media should fit the content rather than forcing every entity into a large image card.

## Phase 6 — Remaining product surfaces

- [ ] Home.
- [ ] Planner/maps.
- [ ] Guild workspace.
- [ ] Raffles/events.
- [ ] Authentication/profile.
- [ ] Admin/operations.

These surfaces may vary in density and information hierarchy, but not in brand fundamentals.

## Phase 7 — Enforcement hardening

- [ ] Remove legacy exceptions from automated checks as migrations land.
- [ ] Fail CI on new Font Awesome imports.
- [ ] Fail CI on hardcoded colors and non-semantic palette utilities.
- [ ] Fail CI on domain SVG literal paint.
- [ ] Add screenshot/reference checks for the canonical component gallery when practical.
- [ ] Require brand/design checks in the standard validation command.

## Definition of migration completion

The migration is complete when:

1. `BRAND_SYSTEM.md` and `DESIGN_SYSTEM.md` describe the actual production UI rather than an aspirational design.
2. The canonical component/reference gallery can reproduce all common TibiaHub product patterns without page-local visual inventions.
3. New features can be built without deciding new colors, radii, icon libraries, card structures, or interaction styling from scratch.
4. Automated checks prevent reintroduction of retired visual patterns.
5. Official documentation and marketing assets are generated from the same canonical identity used by the product.
