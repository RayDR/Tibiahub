# TibiaHub Reference Surface

Cyclopedia is the first TibiaHub reference surface. Its purpose is not only to serve game data; it is the product area used to prove that the brand system can produce real screens consistently.

`/admin/theme-playground` is the living primitive/theme laboratory. It demonstrates reusable controls, states, themes, motion, and density. Cyclopedia is the real-product composition reference that proves those primitives work with TibiaHub data and workflows.

## Reference requirements

The completed reference surface must demonstrate:

- application navigation,
- page header,
- tabs,
- search and filters,
- loading, empty, partial, and error states,
- compact and standard entity cards,
- sprite/GIF handling and fallback behavior,
- badges and stat blocks,
- responsive list/grid behavior,
- pagination or infinite loading,
- scroll restoration,
- entity detail hierarchy,
- coordinates and map integration,
- source/provenance presentation,
- keyboard focus and reduced motion,
- all supported themes without markup forks.

## Canonical entity-card families

### Compact sprite entity

Use for NPCs, items, and other entities where media is intrinsically small.

Required anatomy:

1. sprite/GIF region sized to the content,
2. entity name,
3. up to two high-value metadata fields,
4. optional compact badge/status,
5. shared focus and hover behavior.

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
3. Relationships such as loot, creatures, quests, NPCs, tasks, and requirements.
4. Locations/map/coordinates when applicable.
5. Supporting source/provenance/status information.

## Acceptance test

Cyclopedia becomes the canonical reference implementation only after its entity families no longer require page-local decisions for colors, radii, shadows, generic icons, typography roles, control heights, hover/focus treatment, state presentation, mobile gutters, or responsive breakpoints.
