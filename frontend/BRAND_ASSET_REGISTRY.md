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
| `src/assets/brand/brandTitleIcons.ts` → `maps` | Maps page-title illustration | canonical | Atlas/map artwork. Used as the desktop workspace identity marker without displacing map controls. |
| `src/components/icons/BrandCategoryFallbackIcon.tsx` | Category fallback SVG family | canonical | Theme-safe `currentColor` SVGs for Creatures, Bosses, Loot, Quests, Hunt Zones and NPCs. Used only when real local media is unavailable or fails to render. |
| `GET /api/v1/catalog/category-visuals/daily` | Generic category media selector | canonical | Selects one validated local visual per category from pools of up to 15 items. Selection is stable for the current UTC day and GIF media is preferred when available. |
| `src/styles/brand-system.css` | Canonical product surface treatment | canonical | Shared navigation, page-header, dropdown and stone-panel treatment layered on semantic design-system tokens. |
| `src/assets/brand/brandCategoryIcons.ts` | Former raster category emblems | retired | Removed after browser-invalid inline WebP URLs were observed. Do not restore; use local media first and `BrandCategoryFallbackIcon` second. |
| `src/assets/brand/brandQuestIcon.ts` | Former raster Quest emblem | retired | Removed with the invalid inline category raster assets. |

The large generated background/title artwork is temporarily stored as optimized WebP data URIs because the connected repository write path is text-only. Category/domain fallbacks are not raster data URIs: they are real semantic SVG components so they remain scalable, theme-safe and browser-safe. Future asset-pipeline work may move the remaining approved raster data URIs to binary files without changing their semantic roles.

## Media precedence

TibiaHub distinguishes generic category decoration from entity identity.

1. **Specific entity surfaces** — use that entity's own validated local GIF/sprite/image first. If it is missing or cannot render, use the matching SVG category fallback. Never substitute another entity's daily image.
2. **Generic category surfaces** — use the daily validated local category visual first, then the matching SVG fallback. This applies to surfaces such as Cyclopedia tabs, navigation category menus and Home capability cards.
3. **Maps** — individual markers/results preserve their own media identity; missing marker media falls back to semantic SVG marker artwork rather than another entity's image.
4. **Hunt Planner / Hunt Zone cards** — a mapped zone uses its own map preview; an unmapped zone uses the Hunt Zone SVG fallback.
5. Daily category selection is deterministic for one UTC day so all generic surfaces use the same visual during that day rather than changing on every render.

The daily pools are capped at 15 validated local candidates per category. Loot prefers locally popular items when activity data exists. Quest visuals are selected from quest-like local item media such as books, scrolls, tomes, parchment, letters, documents, journals, diaries, maps, notes, tablets and runes. NPC visuals come only from cached NPC media. The selector filters out assets that are not cached or do not exist on disk.

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
7. Raster `data:image/*` assets are forbidden for category/domain fallbacks. The only temporary raster data-URI exceptions are the explicitly approved product background and page-title artwork until the binary asset pipeline is available.
