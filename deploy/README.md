# Guarded TibiaHub deployment

`deploy/scripts/deploy.sh` is the guarded production deployment entrypoint.
For day-to-day usage, invoke it through `scripts/tibiahub-ops.sh deploy ...`.

Confirmed deployment refuses execution unless:

- local branch is `develop`;
- working tree is clean;
- local `develop` equals `origin/develop`;
- target DB is local PostgreSQL `tibiahub`;
- repository Alembic head matches the expected single revision.

The workflow acquires a deployment lock, captures evidence, builds rollback artifacts, and records per-step stdout/stderr/meta files for diagnosis.

## Deploy

First guarded deployment requires the currently deployed commit:

```bash
deploy/scripts/deploy.sh --confirm-deploy-tibiahub \
  --previous-commit <40-character-deployed-commit>
```

Equivalent consolidated command:

```bash
scripts/tibiahub-ops.sh deploy run --confirm-deploy-tibiahub \
  --previous-commit <40-character-deployed-commit>
```

Dry-run preflight (read-only checks only):

```bash
deploy/scripts/deploy.sh --dry-run
scripts/tibiahub-ops.sh deploy preflight --dry-run
```

## Manual rollback

Use the exact evidence directory produced by deployment:

```bash
deploy/scripts/rollback.sh --confirm-rollback-tibiahub \
  /forge/tibiahub-backups/deployments/<deployment-directory>
```

Equivalent consolidated command:

```bash
scripts/tibiahub-ops.sh deploy rollback --confirm-rollback-tibiahub \
  /forge/tibiahub-backups/deployments/<deployment-directory>
```

## Evidence model

Evidence and state default to `/forge/tibiahub-backups/deployments`.

On failure, deployment preserves:

- `FAILED` (failure metadata);
- `steps/<step>.out.log`;
- `steps/<step>.err.log`;
- `steps/<step>.meta.env`.

Rollback preserves `ROLLBACK_FAILED_INFO` on rollback-step failure.

Alembic downgrade is never used for rollback.
