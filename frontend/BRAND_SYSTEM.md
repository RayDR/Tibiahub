# TibiaHub Brand System

TibiaHub Brand System v1 is the product-level visual contract for TibiaHub.

This document sits above `DESIGN_SYSTEM.md`. The design system defines how UI is implemented; this document defines what TibiaHub is allowed to look and feel like.

## Authority

Visual decisions follow this order:

1. `BRAND_SYSTEM.md` — product identity and visual direction.
2. `DESIGN_SYSTEM.md` — reusable UI contracts and semantic implementation rules.
3. Theme tokens in `src/styles/themes.css`.
4. Shared primitives in `src/components/ui`.
5. Feature and page composition.
6. Legacy code.

A feature must not introduce a visual convention that conflicts with a higher level in this hierarchy.

## Brand position

TibiaHub is a modern companion platform for Tibia. It may reference the game's world through fantasy, exploration, cartography, creatures, loot, quests, and guild activity, but it must remain visually identifiable as TibiaHub rather than imitate the Tibia client.

The product should feel:

- knowledgeable rather than decorative,
- adventurous rather than theatrical,
- game-native rather than game-client imitation,
- dense enough for expert users but readable,
- modern in interaction patterns,
- restrained in animation and visual effects.

## Canonical identity vs. themes

The TibiaHub brand and user-selectable themes are separate concepts.

The canonical TibiaHub identity is represented by the `default` theme and by the official logo, typography, icon language, spacing, shapes, motion, and composition rules in this document.

Other themes (`medieval`, `tibia-stone`, `midnight-arcana`, `blood-moon`, `high-contrast`) are skins. They may alter semantic token values, but they must not redefine component geometry, iconography, typography hierarchy, interaction patterns, or the TibiaHub logo.

Marketing material, documentation screenshots, Open Graph imagery, app-store-style imagery, and official TibiaHub announcements use the canonical identity unless a specific themed example is being demonstrated.

## Typography

TibiaHub uses two roles:

- **Inter** — application body text, controls, data, labels, navigation, tables, forms, and dense information.
- **Cinzel** — product-level headings and selected fantasy-flavored titles only.

Rules:

- Do not use decorative or pixel fonts for application UI.
- Do not use Cinzel for dense data, buttons, tables, inputs, badges, or long paragraphs.
- Use the existing semantic type scale from `design-system.css`.
- Monospace is reserved for coordinates, IDs, numeric/stat data where alignment or technical meaning benefits from it.

## Color

Application code never owns colors. Colors come from semantic tokens.

Feature code must use semantic roles such as:

- `surface`, `surface-raised`, `surface-hover`,
- `text-content-primary`, `text-content-secondary`, `text-content-muted`,
- `primary`, `success`, `warning`, `danger`, `info`, `accent`,
- `border-line`, `border-line-strong`.

Literal colors and Tailwind palette utilities remain forbidden.

The canonical brand palette is the `default` theme. Other themes must remain complete semantic substitutions and may not introduce feature-specific color contracts.

## Shape and elevation

The existing shared radius and elevation tokens are authoritative.

Guidance:

- Small controls and badges: `radius-sm` / `radius-md`.
- Standard cards, search results, list items, menus: `radius-lg`.
- Large panels and feature containers: `radius-xl` when visually justified.
- `radius-2xl` is reserved for major presentation surfaces; it is not the default card radius.
- Pill shapes are reserved for badges, chips, segmented status labels, and compact selectors.

Avoid deeply layered card-within-card-within-card composition. Prefer borders, spacing, dividers, and typography hierarchy before adding additional elevated surfaces.

## Iconography

TibiaHub uses two icon classes:

1. **Interface icons** — Lucide is the canonical UI icon library.
2. **Domain icons** — bespoke TibiaHub SVG components may be used for creatures, categories, loot, quests, locations, vocations, map concepts, and other game-domain concepts where a generic UI icon is insufficient.

Font Awesome is considered migration debt. Existing uses may remain temporarily, but new UI work must not introduce new Font Awesome dependencies. Cyclopedia domain icons should migrate to TibiaHub-owned SVG components over time.

Domain SVG rules:

- `currentColor` by default so semantic colors and themes remain compatible.
- consistent optical size and stroke weight,
- no literal palette values,
- accessible labels belong to the consuming component when the icon conveys meaning,
- decorative icons remain `aria-hidden`.

## Game media

Creature, NPC, item, outfit, boss, and related in-game media are content, not decorative UI chrome.

Rules:

- Preserve original pixel art and GIF animation where available.
- Never blur or stretch sprites to fill arbitrary containers.
- Use `object-contain` for sprite media.
- Prefer compact content-driven containers over large empty image cards.
- Do not apply filters that materially alter game art.
- Hover scaling must be subtle and must not cause layout shifts or crop sprites.
- Missing media must use a deliberate fallback state, never a broken image icon.

## Cyclopedia composition

Cyclopedia is a primary TibiaHub product surface and defines several official patterns.

### Result cards

Result cards should prioritize the entity itself rather than decorative framing.

For compact entities such as NPCs and items:

- sprite/GIF,
- primary name,
- one or two high-value metadata fields,
- optional compact status or category indicators,
- no oversized empty media panel.

For creatures and bosses, larger cards are acceptable when meaningful combat information is visible, but media height must remain proportional to the content.

### Search and filters

- Search, tab selection, and filters use shared controls.
- Active filters remain visible and reversible.
- Mobile layouts must not require horizontal page scrolling.
- Infinite loading or pagination must preserve search context and scroll restoration when supported by the feature.

### Detail pages

Entity detail pages should follow:

1. identity/header,
2. essential stats or metadata,
3. relationships/actions,
4. maps/locations where relevant,
5. supporting source/provenance information when appropriate.

## Maps and coordinates

Map UI should use TibiaHub surfaces and controls around the actual map rather than decorate the map itself.

Coordinates are technical/game data and may use the mono font.

Map markers, paths, labels, and overlays must use semantic/theme-safe tokens where technically possible.

## Navigation and shells

`AppShell`, workspace shells, and shared navigation contracts remain authoritative.

- Primary navigation must remain recognizable across all themes.
- Theme changes do not change navigation information architecture.
- Mobile bottom navigation must preserve minimum touch targets and avoid truncated ambiguity.
- Product logo placement is stable; themes never substitute the logo.

## Motion

Motion communicates state and hierarchy; it is not ambient decoration.

Allowed examples:

- subtle card entrance,
- hover/focus transitions,
- dropdown/dialog transitions,
- tab selection,
- sprite/GIF content animation supplied by game media.

Avoid continuous decorative glow, parallax, pulsing borders, or animation that competes with game media.

`prefers-reduced-motion` remains authoritative.

## Product surfaces

The following product families share the same TibiaHub identity:

- Home,
- Cyclopedia,
- Planner and maps,
- Guild workspace,
- Raffles and events,
- Profile/authentication,
- Admin and operational tools.

Admin may be denser than public/product surfaces, but it is not a separate brand.

## Official asset classes

The brand asset library will be organized around:

- logo / wordmark / compact mark,
- favicon and app icon,
- domain SVG icons,
- separators and patterns,
- background textures/illustrations,
- social/OG templates,
- announcement/banner templates,
- documentation examples.

Generated assets must have a documented role. Assets that exist only because they look decorative are not part of the canonical library.

## Implementation rules

New feature work must:

1. use shared primitives before page-specific styling,
2. use semantic tokens only,
3. use Lucide for generic UI icons,
4. use TibiaHub SVG components for domain-specific concepts,
5. preserve game sprites/GIFs as content,
6. follow shared responsive contracts,
7. keep English and Spanish visible strings translated,
8. pass the design-system, appearance, i18n, layout, TypeScript, and production-build checks.

## Migration policy

Legacy visuals are migrated incrementally. A migration should improve consistency without rewriting working functionality unnecessarily.

When touching an existing feature, prefer moving it toward this contract rather than copying its legacy local styling into new code.

The existence of a legacy pattern is not justification for repeating it.

## Definition of done for visual work

A visual change is complete only when:

- it matches this brand system,
- it consumes shared tokens/primitives,
- it behaves correctly across supported themes,
- responsive behavior is verified,
- keyboard/focus behavior remains valid,
- reduced motion is respected,
- game media has correct sizing/fallback behavior,
- automated design-system checks pass.
