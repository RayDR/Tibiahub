# TibiaHub Brand Migration

This file turns `BRAND_SYSTEM.md` into an incremental implementation plan. It exists so visual consistency work is not reduced to documentation-only output.

## Phase 1 — Foundation

Status: implemented on `design/tibiahub-brand-foundation-v1`.

- [x] Establish `BRAND_SYSTEM.md` as product-level visual authority.
- [x] Separate canonical TibiaHub identity from user-selectable themes.
- [x] Define typography, shape, motion, icon, game-media, Cyclopedia, map, and shell rules.
- [x] Add automated brand validation.
- [x] Make `DESIGN_SYSTEM.md` reference the higher-level brand contract.
- [x] Add `check:brand-system` and aggregate `check:ui` package scripts.
- [x] Add GitHub Actions validation for brand/design/appearance/layouts/i18n, TypeScript, and production build on frontend PRs.

## Phase 2 — Canonical identity assets

- [ ] Rebuild the official logo asset set from one approved source.
- [ ] Produce wordmark, compact mark, favicon, app icon, monochrome mark, and safe-area variants.
- [ ] Define canonical OG/social templates.
- [ ] Define TibiaHub background/pattern library.
- [ ] Document minimum logo size, padding, and misuse examples.

No generated asset becomes canonical until its exact role is documented in `BRAND_SYSTEM.md`.

## Phase 3 — Icon system migration

- [x] Define Lucide as the sole generic interface icon source for new work.
- [x] Baseline existing Font Awesome imports so new usage is rejected without requiring a full rewrite now.
- [ ] Replace Font Awesome Cyclopedia icons with TibiaHub-owned domain SVG components.
- [ ] Migrate remaining generic Font Awesome UI icons to Lucide.
- [ ] Expand `components/icons` for creatures, bosses, loot, quests, zones, NPCs, maps, guild concepts, and other domain concepts only where generic UI icons are insufficient.
- [ ] Remove Font Awesome packages once no application imports remain.
- [ ] Remove migration allowlist entries as each legacy import disappears.

## Phase 4 — Living component reference

`/admin/theme-playground` is the current live primitive/theme gallery and should be evolved rather than replaced by a second documentation-only page.

- [x] Buttons and action variants.
- [x] Badges/status tones.
- [x] Inputs, selects, textareas, and form fields.
- [x] Dropdown/dialog examples.
- [x] Loading, empty, alert, and skeleton states.
- [x] Tables/data display.
- [x] Theme, motion, and density preview.
- [ ] Add explicit TibiaHub brand guidance to the playground UI.
- [ ] Add canonical entity-card examples for compact sprite entities, combat entities, and location entities.
- [ ] Add game sprite/GIF media examples and fallback states.
- [ ] Add domain-icon examples next to generic Lucide examples.

The playground demonstrates primitives. Cyclopedia demonstrates how those primitives compose into real product screens.

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
- [x] Fail validation on new Font Awesome imports outside the explicit legacy baseline.
- [x] Continue using the existing design-system check for hardcoded colors and non-semantic palette utilities.
- [x] Fail validation on domain SVG literal paint.
- [ ] Add screenshot/reference checks for the canonical component gallery when practical.
- [x] Require brand/design checks in the standard frontend UI validation command.

## Definition of migration completion

The migration is complete when:

1. `BRAND_SYSTEM.md` and `DESIGN_SYSTEM.md` describe the actual production UI rather than an aspirational design.
2. The live component/reference gallery can reproduce all common TibiaHub product patterns without page-local visual inventions.
3. New features can be built without deciding new colors, radii, icon libraries, card structures, or interaction styling from scratch.
4. Automated checks prevent reintroduction of retired visual patterns.
5. Official documentation and marketing assets are generated from the same canonical identity used by the product.
