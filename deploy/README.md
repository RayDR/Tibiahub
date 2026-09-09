# Guarded TibiaHub deployment

The supported day-to-day entrypoint is:

```bash
scripts/tibiahub-ops.sh
```

The lower-level scripts in `deploy/scripts/` remain available for automation and recovery, but operators should normally use the consolidated CLI.

## Command model

Normal deployment from an allowed branch:

```bash
scripts/tibiahub-ops.sh deploy
```

Read-only deployment preflight:

```bash
scripts/tibiahub-ops.sh deploy dry-run
```

Current deployment and recent evidence:

```bash
scripts/tibiahub-ops.sh deploy status
```

Recent deployment history:

```bash
scripts/tibiahub-ops.sh deploy history
```

Rollback the currently recorded deployment:

```bash
scripts/tibiahub-ops.sh deploy rollback
```

A rollback is destructive because it restores the database snapshot as well as application state. Interactive sessions therefore ask for approval. For non-interactive automation, use:

```bash
scripts/tibiahub-ops.sh deploy rollback --confirm-rollback
```

To roll back from a specific historical evidence directory:

```bash
scripts/tibiahub-ops.sh deploy rollback \
  20260909T120000Z-0123456789ab
```

An absolute deployment evidence path is also accepted.

## Branch policy

Deployments are no longer restricted to `develop`.

The script resolves the deployment environment from:

1. `TIBIAHUB_DEPLOY_ENV`, when set;
2. otherwise `APP_ENV`, when set;
3. otherwise `development`.

Environment aliases such as `dev`, `stage`, `staging`, and `test` use the development branch policy. `prod` and `production` use the production policy.

### Development

Standard branches are:

- the repository default branch;
- `develop`.

### Production

Standard branches are:

- the repository default branch;
- `main`;
- `master`.

Any other named branch may still be deployed. The deploy prints a warning and asks for interactive approval.

For automation, or when the operator intentionally wants to bypass that prompt:

```bash
scripts/tibiahub-ops.sh deploy --confirm-deploy
```

`--confirm-deploy` does **not** bypass other safety checks. The working tree must still be clean, the branch must exist on `origin`, and the local branch commit must equal the matching remote branch commit exactly.

A dry-run on a non-standard branch does not require confirmation. It emits the warning and continues because it does not mutate the deployment.

## Automatic rollback snapshot

Every real deployment establishes rollback evidence before services are stopped or migrations are applied.

The evidence directory contains or records:

- the exact previous deployed commit;
- a protected Git ref under `refs/tibiahub/deploy-snapshots/...` so the previous commit remains reachable locally;
- the target branch and target commit;
- the deployment environment and repository default branch;
- the previous and target Alembic revisions;
- a validated PostgreSQL custom-format dump plus SHA-256;
- an extension-preserving restore catalog;
- the previous frontend build;
- the previous backend runtime;
- PM2 process state;
- per-step stdout, stderr, timing, and failure evidence.

The current deployment is recorded at:

```text
/forge/tibiahub-backups/deployments/current.env
```

Because this state points at the deployment evidence directory, the normal rollback command does not require copying an evidence path manually:

```bash
scripts/tibiahub-ops.sh deploy rollback
```

`--previous-commit <sha40>` is retained only as a bootstrap/recovery escape hatch when no valid deployment state or successful prior evidence can be discovered automatically.

## Git safety

A real deploy requires:

- a named branch (detached HEAD is refused);
- a completely clean working tree;
- the branch to exist on `origin`;
- local `HEAD` to equal `origin/<current-branch>` exactly.

This applies equally to standard and explicitly approved non-standard branches.

## Database safety

The deployment still requires:

- the target database to be the local PostgreSQL `tibiahub` database;
- exactly one Alembic HEAD;
- a valid upgrade path from the deployed revision to the release revision;
- a validated database snapshot before migration.

Alembic downgrade is never used for rollback. Rollback restores the validated pre-deploy database snapshot.

## Versioned backend Python runtime

Backend dependencies are built into a commit-specific virtual environment under:

```text
/forge/tibiahub-runtimes/<commit>
```

The active runtime is selected atomically through `backend/runtime-current`. PM2 backend services execute Python from that link instead of modifying the legacy `backend/venv` in place.

A candidate runtime must install the pinned `backend/requirements.txt`, pass `pip check`, import the required runtime packages, and complete all normal deployment preflights before services are stopped.

Deployment metadata records both the candidate and previous runtime. Rollback restores the prior runtime link together with the prior commit, database snapshot, frontend build, and PM2 process state.

The legacy `backend/venv` remains a compatibility fallback for deployments created before versioned runtimes were introduced.

PM2 service definitions are recreated during deployment and rollback so executable-path changes are applied instead of reloading a stale registered runtime.

## Compatibility aliases

The old forms remain accepted temporarily and emit deprecation warnings:

```text
deploy run ...
deploy preflight --dry-run
--confirm-deploy-tibiahub
--confirm-rollback-tibiahub
```

New operational documentation and automation should use the shorter command model described above.
