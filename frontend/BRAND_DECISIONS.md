# TibiaHub Brand Decisions

This log records explicit product-level visual decisions so future work does not have to infer intent from whichever screen was implemented most recently.

## B-001 — Brand outranks legacy UI

**Decision:** `BRAND_SYSTEM.md` is the highest visual authority. Existing UI is implementation evidence, not a design specification.

## B-002 — Brand and themes are separate

**Decision:** `tibia-stone` represents the canonical/default TibiaHub product identity in the current appearance system. The other themes are user-selectable skins.

**Consequences:** Themes may change semantic colors, but they do not redefine logo, typography roles, component geometry, icon language, information architecture, or interaction patterns. The legacy stored value `default` migrates to `tibia-stone` and is not a separate theme.

## B-003 — Inter + Cinzel remain the initial typography contract

**Decision:** Inter remains the application/body/data typeface. Cinzel remains a restrained heading/display typeface.

**Consequences:** Pixel fonts and decorative fantasy fonts are not application UI fonts. This decision can be revisited only as a brand-level change, not per feature.

## B-004 — Lucide is the generic UI icon source

**Decision:** Generic interface actions and navigation use Lucide.

**Consequences:** New Font Awesome UI usage is not allowed. Existing Font Awesome imports are migration debt. Domain concepts may use TibiaHub-owned SVG components.

## B-005 — Game art is content

**Decision:** Sprites, GIFs, items, outfits, NPCs, creatures, and bosses are treated as source content, not UI decoration.

**Consequences:** Containers adapt to content; game art is not stretched, blurred, recolored, or forced into oversized decorative media areas.

## B-006 — Cyclopedia is the first reference surface

**Decision:** Cyclopedia will be the first product area fully normalized against the brand system.

**Why:** It exercises search, tabs, filters, cards, sprites/GIFs, stats, maps, coordinates, detail pages, responsive behavior, and multiple entity types.

## B-007 — Documentation must be executable

**Decision:** Every stable brand rule that can be checked mechanically should eventually be represented in automated validation.
