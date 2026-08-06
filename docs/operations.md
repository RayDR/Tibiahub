# TibiaHub operations guide

## Primary interface

Use `scripts/tibiahub-ops.sh` for routine operations. It centralizes confirmations, dry-run diagnostics, and dispatches to guarded scripts.

```bash
scripts/tibiahub-ops.sh help
```

## Fast diagnostics

```bash
scripts/tibiahub-ops.sh status
scripts/tibiahub-ops.sh services status
scripts/tibiahub-ops.sh health
scripts/tibiahub-ops.sh diagnose
```

## Database operations

Read-only validation:

```bash
scripts/tibiahub-ops.sh db verify --dry-run
scripts/tibiahub-ops.sh db revision
scripts/tibiahub-ops.sh db revision current
scripts/tibiahub-ops.sh db revision heads
scripts/tibiahub-ops.sh db revision history
scripts/tibiahub-ops.sh db revision check
```

Destructive operations require explicit confirmation:

```bash
scripts/tibiahub-ops.sh db provision --confirm-provision-tibiahub
scripts/tibiahub-ops.sh db migrate --confirm-migrate-tibiahub
scripts/tibiahub-ops.sh db backup
scripts/tibiahub-ops.sh db restore --confirm-restore-tibiahub /absolute/path/to/backup.dump
scripts/tibiahub-ops.sh db reset --confirm-reset-tibiahub
```

Dry-run coverage for mutation-prone commands:

```bash
scripts/tibiahub-ops.sh db provision --dry-run
scripts/tibiahub-ops.sh db migrate --dry-run
scripts/tibiahub-ops.sh db restore --dry-run /absolute/path/to/backup.dump
scripts/tibiahub-ops.sh db reset --dry-run
scripts/tibiahub-ops.sh services restart --dry-run tibiahub-api
scripts/tibiahub-ops.sh spatial rebuild --dry-run
scripts/tibiahub-ops.sh secrets generate --dry-run
scripts/tibiahub-ops.sh deploy preflight --dry-run
```

## Spatial operations

```bash
scripts/tibiahub-ops.sh spatial verify --dry-run
scripts/tibiahub-ops.sh spatial rebuild --dry-run
scripts/tibiahub-ops.sh spatial rebuild --execute --confirm-rebuild-spatial-links
```

## Deployment and rollback

Dry-run preflight (no deploy mutation):

```bash
scripts/tibiahub-ops.sh deploy preflight --dry-run
```

Confirmed deploy:

```bash
scripts/tibiahub-ops.sh deploy run --confirm-deploy-tibiahub --previous-commit <sha40>
```

Rollback from evidence directory:

```bash
scripts/tibiahub-ops.sh deploy rollback --confirm-rollback-tibiahub /forge/tibiahub-backups/deployments/<evidence-dir>
```

## Evidence and failure diagnosis

Deployment and rollback preserve evidence directories and write per-step logs:

- `steps/<step>.out.log`
- `steps/<step>.err.log`
- `steps/<step>.meta.env`
- `FAILED` or `ROLLBACK_FAILED_INFO`

Use the `stderr_log` and `stdout_log` paths recorded in failure metadata to inspect the exact failing command output.

## Safety model

- Operational entrypoint scripts refuse sourcing and must be executed directly.
- Secret files must be absolute, owned by the deploy user, and mode `0600`.
- Deploy/rollback use an exclusive lock file under the deploy evidence root.
- Rollback uses snapshots and evidence metadata, not Alembic downgrade.

## Related docs

- `deploy/README.md`
- `docs/POSTGRES_MIGRATION.md`
- `docs/operations-script-inventory.md`
- `docs/operations-user-guide.md`
