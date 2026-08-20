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
- The rollback frontend is built with `npm ci` from the previous commit's own `package-lock.json` instead of borrowing the current release's dependencies.

## Recorded deployment reconciliation

`current.env` is normally authoritative for the previous deployed commit. A manual deployment can make that recorded state stale because the guarded deploy did not get a chance to write its state file.

- Without `--previous-commit`, deploy continues to use the recorded `deployed_commit`.
- When `--previous-commit <sha40>` is supplied explicitly, that operator-provided commit becomes the rollback base for the deployment.
- If the explicit value differs from `current.env`, deploy emits a warning instead of aborting and records both the explicit and previously recorded commits in deployment metadata.
- The explicit commit must still be a valid 40-character Git commit available in the repository.
- A successful guarded deployment rewrites `current.env`, bringing recorded state back in sync automatically.

This is intended for conscious recovery from an out-of-band/manual deployment; deploy does not try to guess an unrecorded previous commit on its own.

The deploy repairs deterministic local prerequisites such as missing frontend dependencies. It still fails safely rather than guessing when dependency installation, migration topology, database validation, builds, health checks, or service checks genuinely fail.
