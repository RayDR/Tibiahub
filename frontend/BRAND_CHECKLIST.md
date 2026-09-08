# TibiaHub Visual Change Checklist

Use this checklist for visual/product PRs until equivalent checks are automated.

- [ ] Change follows `BRAND_SYSTEM.md`.
- [ ] Shared primitive used where one exists.
- [ ] No hardcoded colors or Tailwind palette colors.
- [ ] No new Font Awesome import.
- [ ] Generic UI icons use Lucide.
- [ ] Domain SVG uses theme-safe paint (`currentColor` where appropriate).
- [ ] Sprite/GIF uses contained sizing and has a fallback.
- [ ] No unnecessary oversized media frame for compact game entities.
- [ ] Focus-visible behavior works by keyboard.
- [ ] Reduced-motion behavior remains valid.
- [ ] Mobile layout does not horizontally overflow.
- [ ] Visible strings are translated in English and Spanish.
- [ ] All supported themes work without feature markup forks.
- [ ] `node scripts/check-brand-system.mjs` passes.
- [ ] `npm run check:design-system` passes.
- [ ] `npm run check:appearance` passes.
- [ ] `npm run check:i18n` passes.
- [ ] `npm run check:layouts` passes when layout is affected.
- [ ] TypeScript and production build pass.
