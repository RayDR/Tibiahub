# TibiaHub Reference Surface

TibiaHub uses two complementary living references:

1. `/admin/theme-playground` is the primitive/theme laboratory. It proves shared components, semantic tokens, states, motion, density, overlays, and theme substitution in real application code.
2. Cyclopedia is the first complete product reference surface. It proves that those primitives compose into coherent real screens with game media, search, filters, entity relationships, maps, coordinates, and responsive browsing.

The manual is expected to document these real implementations rather than maintain a separate idealized mockup.

## Reference requirements

The completed Cyclopedia reference surface must demonstrate:

- application navigation,
- page header,
- tabs,
- search,
- filters,
- loading, empty, and error states,
- compact and standard entity cards,
- sprite/GIF handling,
- badges and stat blocks,
- responsive list/grid behavior,
- infinite loading or pagination,
- scroll restoration,
- entity detail hierarchy,
- coordinates,
- map integration,
- source/provenance presentation,
- keyboard focus,
- reduced motion,
- all supported themes without markup changes.

## Canonical entity-card families

### Compact sprite entity

Use for NPCs, items, and other entities where the media is intrinsically small.

Required anatomy:

1. sprite/GIF region sized to the content,
2. entity name,
3. up to two high-value metadata fields,
4. optional compact badge/status,
5. entire card/link uses shared focus and hover behavior.

Avoid tall empty image panels.

### Combat entity

Use for creatures and bosses when stats are part of the browsing decision.

Required anatomy:

1. contained sprite/media,
2. entity name,
3. classification/status where useful,
4. concise stat group,
5. optional task/context indicator.

The media area must not dominate the information hierarchy by default.

### Rich location/zone entity

Use for hunt zones and other location-driven entities.

Required anatomy:

1. name and location identity,
2. key suitability metadata,
3. compact relationship/entity indicators,
4. optional map/location affordance.

## Detail-page skeleton

1. `PageHeader` / identity.
2. Primary metadata or combat stats.
3. Relationships (loot, creatures, quests, NPCs, tasks, requirements as applicable).
4. Locations/map/coordinates when applicable.
5. Supporting source/provenance/status information.

## Acceptance test

Cyclopedia can be declared the canonical reference implementation only after its entity families no longer require page-local decisions for:

- colors,
- radius,
- shadows,
- generic icons,
- typography roles,
- control heights,
- card hover/focus treatment,
- loading/empty/error presentation,
- mobile gutters and responsive breakpoints.

Once that is true, new TibiaHub entity-driven features should compose the same primitives rather than invent replacements.
