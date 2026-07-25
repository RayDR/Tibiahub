# TibiaHub Design System

Stage 3.0.1 establishes a single visual language for every TibiaHub screen. The source of truth is `src/styles/design-system.css`; Tailwind exposes the same semantic colors through `tailwind.config.js`, and reusable React primitives live in `src/components/ui`.

## Principles

- Components describe meaning (`primary`, `danger`, `surface-raised`) instead of palette values.
- Themes change token values, never component markup.
- Controls are keyboard accessible, mobile-first, and share focus, disabled, hover, and active states.
- Product or guild-specific styling may compose tokens, but must not introduce colors.
- `npm run check:design-system` rejects hardcoded component colors, legacy palette utilities, incomplete themes, and missing layout primitives.

## Color tokens

All themes define RGB channel tokens (`--ds-*`) so Tailwind opacity modifiers such as `bg-primary/20` work. Components use the semantic aliases below.

| Group | Tokens | Purpose |
| --- | --- | --- |
| Surfaces | `--surface-base`, `--surface`, `--surface-raised`, `--surface-hover`, `--surface-active`, `--surface-overlay`, `--surface-inverse` | Page, panel, interactive, overlay, and inverse backgrounds |
| Brand | `--primary`, `--primary-hover`, `--primary-active`, `--primary-subtle` | Primary actions, selection, and product emphasis |
| Status | `--success`, `--warning`, `--danger`, `--info`, `--accent` and each `*-subtle` token | Semantic feedback and category emphasis |
| Text | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-inverse`, `--text-on-primary` | Content hierarchy and contrasting text |
| Lines | `--border`, `--border-strong`, `--border-focus` | Dividers, strong outlines, and keyboard focus |

Tailwind equivalents are `bg-surface[-raised|-hover]`, `text-content-primary`, `text-content-secondary`, `text-content-muted`, `border-line[-strong]`, `ring-line-focus`, and the `primary`, `success`, `warning`, `danger`, `info`, and `accent` families. Opacity modifiers are supported.

The available themes are `default`, `medieval`, and `tibia-stone`. Every theme supplies every color channel. Compatibility aliases exist only for specialized legacy class names; new code must use semantic names.

## Foundation tokens

| Group | Tokens |
| --- | --- |
| Typography | `--font-body`, `--font-heading`, `--font-mono`; `--font-size-xs` through `--font-size-4xl` and `--font-size-display`; `--line-height-tight`, `--line-height-normal`, `--line-height-relaxed`; regular, medium, semibold, and bold weights |
| Spacing | `--space-0`, `--space-1`, `--space-2`, `--space-3`, `--space-4`, `--space-5`, `--space-6`, `--space-8`, `--space-10`, `--space-12`, `--space-16`, `--space-20`, `--space-24` |
| Shape | `--radius-none`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`, `--radius-2xl`, `--radius-full` |
| Opacity | `--opacity-disabled`, `--opacity-muted`, `--opacity-overlay` |
| Elevation | `--elevation-0`, `--elevation-1`, `--elevation-2`, `--elevation-3`, `--elevation-overlay` |
| Motion | `--ease-standard`, `--ease-emphasized`; `--duration-instant`, `--duration-fast`, `--duration-base`, `--duration-slow`, `--duration-slower` |
| Stacking | `--z-base`, `--z-dropdown`, `--z-sticky`, `--z-overlay`, `--z-modal`, `--z-toast`, `--z-tooltip` |
| Controls/icons | `--control-height-sm`, `--control-height-md`, `--control-height-lg`; `--icon-size-xs`, `--icon-size-sm`, `--icon-size-md`, `--icon-size-lg`, `--icon-size-xl` |

Motion automatically collapses under `prefers-reduced-motion: reduce`.

## Layout primitives

Import from `components/ui`:

- `Container`: centered, responsive page-width constraint.
- `Page`: standard vertical page spacing.
- `Section`: consistent content grouping and gap.
- `Panel`: elevated section surface.
- `Card`: reusable content card surface.
- `Toolbar`: wrapping action/filter row.
- `SplitView`: responsive content/sidebar grid; use `sidebarPosition="start"` when required.
- `Sidebar`: sticky desktop rail that remains fluid on mobile.
- `ScrollablePanel`: bounded horizontal/vertical overflow area.

The breakpoints are mobile-first: base styles support phones, container gutters expand at 640px, and split views become two columns at 1024px.

## Components

| Component | Contract |
| --- | --- |
| `AppButton` | `primary`, `secondary`, `ghost`, and `danger` variants; `sm`, `md`, and `lg` sizes; disabled and loading states |
| `AppCard` / `Card` / `Panel` | Standard border, radius, surface, and elevation; `AppCard alt` selects the raised surface |
| `AppInput`, `Input`, `Select`, `Textarea` | Shared height, radius, placeholder, hover, focus, error-compatible, and disabled behavior |
| `FormField` | Associates label/help/error text and ARIA state with one control |
| `AppTabs` | Scrollable tab list with active, hover, keyboard-focus, and ARIA selection states |
| `Badge` | Neutral, primary, success, warning, danger, and info tones |
| `Alert` | Semantic live feedback using the same tone set |
| `Dialog` | Modal surface and dismissible backdrop with modal semantics |
| `Dropdown` | Menu surface with standard stacking and elevation |
| `Tooltip` | Compact explanatory overlay with tooltip semantics |
| `TableContainer` / `Table` | Responsive overflow, consistent cells, headers, dividers, and row hover |
| `EmptyState` | Icon, title, description, and optional recovery action |
| `LoadingState` | Live-region loading feedback and tokenized spinner |
| `Skeleton` | Reduced-motion-aware placeholder animation |
| `PageHeader` | Product heading typography, optional icon/subtitle, and responsive size |

## Usage rules

1. Prefer a shared primitive before adding page-specific CSS.
2. Use semantic utilities such as `bg-surface`, `text-content-secondary`, and `border-danger/40`; never use Tailwind palette names or literal color values.
3. Use the spacing scale and standard radii. Preserve a custom size only when it represents content geometry rather than visual styling.
4. Keep visible strings translated in both English and Spanish.
5. Verify new work with `npm run check:design-system`, `npm run check:i18n`, TypeScript, and the production build.
