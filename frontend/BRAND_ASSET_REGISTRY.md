# TibiaHub Brand Asset Registry

This registry prevents the asset library from becoming a collection of unowned decorative files. Every canonical asset must have one documented role.

## Status vocabulary

- `canonical` — approved for production and official communications.
- `candidate` — being evaluated; not yet authoritative.
- `legacy` — may remain in existing UI but must not be copied into new work.
- `retired` — must not be used.

## Current assets

| Asset | Role | Status | Notes |
| --- | --- | --- | --- |
| `/assets/logo/tibiahub.png` | Current application logo | legacy | Retain until the canonical logo set is rebuilt. |
| `/assets/buttons/menu-btn-normal.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `/assets/buttons/menu-btn-hover.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `/assets/buttons/menu-btn-active.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `src/assets/brand/brandBackground.ts` | Canonical product-world background | canonical | Generated moonlit citadel landscape; optimized WebP data URI used by the shared app shell. Admin intentionally does not use this ambience. |
| `src/assets/brand/brandTitleIcons.ts` → `cyclopedia` | Cyclopedia page-title illustration | canonical | Open grimoire. Used automatically by the shared `PageHeader` on `/cyclopedia`. |
| `src/assets/brand/brandTitleIcons.ts` → `huntPlanner` | Hunt Planner page-title illustration | canonical | Route/planner scroll. Used automatically by the shared `PageHeader` on `/planner`. |
| `src/assets/brand/brandTitleIcons.ts` → `maps` | Maps page-title illustration | canonical | Atlas/map artwork. Registered for the map workspace; placement must respect the full-screen map controls. |
| `src/assets/brand/brandCategoryIcons.ts` → `creatures` | Cyclopedia Creatures emblem | canonical | Gold paw emblem used by top-level category navigation. |
| `src/assets/brand/brandCategoryIcons.ts` → `bosses` | Cyclopedia Bosses emblem | canonical | Gold skull emblem used by top-level category navigation. |
| `src/assets/brand/brandCategoryIcons.ts` → `items` | Cyclopedia Loot emblem | canonical | Loot pouch emblem used by top-level category navigation. |
| `src/assets/brand/brandCategoryIcons.ts` → `quests` | Cyclopedia Quests emblem | canonical | Quest scroll emblem used by top-level category navigation. |
| `src/assets/brand/brandCategoryIcons.ts` → `zones` | Cyclopedia Hunt Zones emblem | canonical | Route/compass emblem used by top-level category navigation. |
| `src/assets/brand/brandCategoryIcons.ts` → `npcs` | Cyclopedia NPCs emblem | canonical | NPC medallion used by top-level category navigation. |

The first production assets are stored as optimized WebP data URIs because the connected repository write path is text-only. Their visual source is the approved generated TibiaHub artwork. Future asset-pipeline work may move the same assets to binary files without changing their semantic roles.

## Required canonical asset set

| Class | Required variants |
| --- | --- |
| Logo | primary horizontal, compact mark, monochrome light, monochrome dark |
| App identity | favicon SVG/ICO/PNG sizes, app icon |
| Social | Open Graph default, announcement/banner template |
| Domain icons | Cyclopedia tabs and recurring TibiaHub-only domain concepts |
| Backgrounds | default product background treatment, optional documented pattern/texture |
| Documentation | canonical screenshot/component-gallery templates |

## Asset rules

1. New canonical assets must be referenced here.
2. A file is not canonical merely because it exists under `public/assets`.
3. Theme-specific product skins do not get alternate TibiaHub logos.
4. In-game sprites/GIFs are content assets and do not need entries here unless TibiaHub redistributes a curated static asset directly.
5. SVG brand/domain assets should support theme-safe rendering where appropriate; generic UI icons remain Lucide components rather than copied SVG files.
6. Generated brand art used in production must be optimized before shipping and must not replace pixel-art/game media used as entity content.
