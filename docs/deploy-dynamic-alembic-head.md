# Guarded deploy self-preparation

The guarded deploy resolves release state from the commit being deployed instead of relying on manually maintained assumptions.

## Alembic target

- Deploy requires exactly one Alembic head.
- The resolved revision is reused for upgrade-path validation, deployment metadata, post-upgrade verification, and deployment state.
- Multiple heads or an invalid revision identifier stop the deploy during preflight before services are touched.
- Do not hardcode the latest revision in `deploy/scripts/deploy.sh` when adding migrations.

## Frontend dependencies

- `package.json` and `package-lock.json` are fingerprinted together using content-only, path-independent hashes.
- If `frontend/node_modules` is missing or its recorded fingerprint is stale, preflight runs `npm ci --prefer-offline --no-audit --no-fund` automatically before the frontend build.
- A successful preparation writes the dependency fingerprint under `frontend/node_modules` so unchanged releases can reuse the installed tree.
- Symlinked `frontend/node_modules` is rejected rather than mutated, because deploy must not accidentally alter another checkout through a symlink.
- The rollback frontend is built with `npm ci` from the previous commit's own lockfile instead of borrowing the current release's dependencies.

The deploy should repair deterministic local prerequisites such as missing frontend dependencies. It should still fail safely rather than guess when dependency installation, migration topology, database validation, builds, health checks, or service checks genuinely fail.
