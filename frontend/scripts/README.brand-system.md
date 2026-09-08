# Brand-system validation

Run `node scripts/check-brand-system.mjs` from `frontend/` to validate the product-level TibiaHub visual contract.

The check currently enforces:

- presence of the required brand-governance sections,
- canonical default theme availability,
- Inter/Cinzel/mono typography contracts,
- shared radius and motion foundations,
- no new Font Awesome imports outside the explicit migration baseline,
- theme-safe paint in TibiaHub-owned domain SVG components,
- linkage between `DESIGN_SYSTEM.md` and the higher-level brand contract.

The migration baseline is intentionally explicit. As legacy icon usage is removed, delete its allowlist entries so the validator becomes stricter over time.
