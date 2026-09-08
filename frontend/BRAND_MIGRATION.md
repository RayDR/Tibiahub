# TibiaHub Brand Migration

This file turns `BRAND_SYSTEM.md` into an incremental implementation plan. The foundation is intentionally based on the current `develop` branch so it can evolve with V1.4 without reintroducing older frontend states.

## Phase 1 — Foundation

Status: integrated on a branch created directly from current `develop`.

- [x] Establish `BRAND_SYSTEM.md` as product-level visual authority.
- [x] Separate canonical TibiaHub identity from user-selectable themes.
- [x] Define typography, shape, motion, icon, game-media, Cyclopedia, map, and shell rules.
- [x] Add automated brand validation.
- [x] Make `DESIGN_SYSTEM.md` reference the higher-level brand contract.
- [x] Add `check:brand-system` to the existing frontend validation flow.
- [x] Add GitHub Actions validation for frontend PRs without replacing current V1.4 checks.

## Phase 2 — Canonical identity assets

- [ ] Rebuild the official logo asset set from one approved source.
- [ ] Produce wordmark, compact mark, favicon, app icon, monochrome light, and monochrome dark variants.
- [ ] Define canonical OG/social templates.
- [ ] Define TibiaHub background/pattern library.
- [ ] Document minimum logo size, padding, and misuse examples.

No generated asset becomes canonical until its exact role is documented in `BRAND_ASSET_REGISTRY.md` and reflected by production usage.

## Phase 3 — Icon system migration

- [x] Define Lucide as the generic interface icon source for new work.
- [ ] Baseline all remaining Font Awesome imports on current `develop` and prevent the debt from expanding.
- [ ] Replace Font Awesome Cyclopedia icons with TibiaHub-owned domain SVG components.
- [ ] Migrate generic Font Awesome UI icons to Lucide.
- [ ] Expand `components/icons` only for TibiaHub/domain concepts where generic icons are insufficient.
- [ ] Remove Font Awesome packages when no application imports remain.

## Phase 4 — Living component reference

`/admin/theme-playground` is the live primitive/theme laboratory and should be evolved rather than replaced by a parallel documentation-only page.

- [x] Buttons, badges, forms, overlays, loading/empty states, tables, themes, motion, and density already exist.
- [ ] Add explicit TibiaHub brand guidance.
- [ ] Add canonical compact-sprite, combat-entity, and location-entity examples.
- [ ] Add sprite/GIF and media fallback examples.
- [ ] Add domain-icon examples beside generic Lucide examples.

The playground demonstrates primitives. Cyclopedia demonstrates real product composition.

## Phase 5 — Cyclopedia reference implementation

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

NPC compact cards are the reference for small sprite-driven entities: media should fit the entity rather than force an oversized media frame.

## Phase 6 — Remaining product surfaces

- [ ] Home.
- [ ] Planner/maps.
- [ ] Guild workspace.
- [ ] Raffles/events.
- [ ] Authentication/profile.
- [ ] Admin/operations.

## Phase 7 — Enforcement hardening

- [ ] Remove legacy exceptions as migrations land.
- [ ] Fail validation on any new Font Awesome import after the current develop baseline is recorded.
- [x] Continue using the existing design-system check for hardcoded colors and non-semantic palette utilities.
- [x] Fail validation on literal paint in TibiaHub-owned domain SVGs.
- [ ] Add screenshot/reference checks when practical.
- [x] Include brand validation in the standard frontend `npm run check` flow.

## Definition of migration completion

The migration is complete when:

1. `BRAND_SYSTEM.md` and `DESIGN_SYSTEM.md` describe the actual production UI rather than an aspirational mockup.
2. The live component/reference gallery reproduces common TibiaHub patterns without page-local visual inventions.
3. New features do not decide new colors, radii, icon libraries, card structures, or interaction styling from scratch.
4. Automated checks prevent reintroduction of retired patterns.
5. Official logo/manual/social/SVG resources come from the same canonical identity used by the product.
