# TibiaHub Component Ownership Policy

A visual pattern should exist at the lowest stable reusable level that owns its meaning.

## Shared UI primitives

Use `src/components/ui` for product-agnostic application behavior such as buttons, cards, inputs, tabs, tables, dialogs, feedback states, headers, and layout primitives.

## Domain components

Use domain folders for repeated TibiaHub concepts such as:

- Cyclopedia entity cards,
- map/coordinate controls,
- guild-specific workflow widgets,
- raffle/event domain components.

Domain components may compose shared UI primitives but must not redefine the global visual language.

## Page-local styling

Page-local visual rules are acceptable only for content geometry or one-off composition. They must not establish new colors, control styles, radii, icon systems, elevation systems, or animation conventions.

## Promotion rule

Promote a pattern into a shared component when either:

1. two or more surfaces need the same visual/interaction behavior, or
2. the pattern is an explicit brand/product contract even if currently used once.

## Deprecation rule

When a shared primitive replaces a legacy local pattern, new code must use the shared primitive immediately. Existing legacy usage can migrate incrementally, but the retired pattern must not spread.
