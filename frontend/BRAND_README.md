# TibiaHub Brand System Entry Point

For product/visual work, read these files in this order:

1. `BRAND_SYSTEM.md` — visual/product authority.
2. `BRAND_DECISIONS.md` — recorded decisions and rationale.
3. `DESIGN_SYSTEM.md` — implementation primitives and semantic tokens.
4. `BRAND_REFERENCE_SURFACE.md` — Cyclopedia reference patterns.
5. `BRAND_MIGRATION.md` — migration sequence.
6. `BRAND_ASSET_REGISTRY.md` — canonical/legacy asset status.
7. `BRAND_CHECKLIST.md` — PR validation checklist.

Executable validation:

```bash
node scripts/check-brand-system.mjs
npm run check:design-system
npm run check:appearance
npm run check:i18n
npm run check:layouts
```

The long-term goal is to expose `check:brand-system` through `package.json` and include it in the normal validation/CI path.
