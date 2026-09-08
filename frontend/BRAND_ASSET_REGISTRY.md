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
| `/assets/logo/tibiahub.png` | Current application logo | legacy | Source asset is large PNG; retain until the canonical logo set is rebuilt. |
| `/assets/buttons/menu-btn-normal.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `/assets/buttons/menu-btn-hover.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `/assets/buttons/menu-btn-active.svg` | Historical navigation/button art | legacy | Do not introduce into new generic UI. |
| `/assets/guild/bw-ash.png` | Guild-specific media | legacy | Content/artwork, not a global TibiaHub brand primitive. |
| `/assets/guild/bw_fire.png` | Guild-specific media | legacy | Content/artwork, not a global TibiaHub brand primitive. |

## Required canonical asset set

The following assets must eventually become `canonical`:

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
