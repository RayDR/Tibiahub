# TibiaHub operations user guide

## 1) Purpose

TibiaHub operational tooling provides guarded command paths for diagnostics, database lifecycle tasks, service control, and deployment/rollback orchestration while preserving evidence and requiring explicit confirmations for destructive operations.

## 2) Directory and component overview

- Main CLI: `scripts/tibiahub-ops.sh`
- Shared libraries:
  - `scripts/lib/ops-common.sh`
  - `scripts/lib/postgres.sh`
- Guarded deployment boundaries:
  - `deploy/scripts/deploy.sh`
  - `deploy/scripts/rollback.sh`
- Specialized implementation scripts (retained):
  - database backup/restore/reset/provision
  - secrets generation
  - spatial rebuild/verification
  - admin bootstrap

## 3) Rule: execute entrypoints, never source them

Operational entrypoints must be executed directly. If sourced, they refuse safely and return non-zero without terminating the caller shell.

## 4) Main CLI help and command structure

```bash
scripts/tibiahub-ops.sh help
```

Top-level commands:

- `help`
- `status`
- `health`
- `diagnose`
- `db ...`
- `spatial ...`
- `services ...`
- `admin ...`
- `secrets ...`
- `deploy ...`
- `media ...`

## 5) Safe/read-only commands

- `scripts/tibiahub-ops.sh status`
- `scripts/tibiahub-ops.sh health`
- `scripts/tibiahub-ops.sh services status`
- `scripts/tibiahub-ops.sh db status`
- `scripts/tibiahub-ops.sh db verify --dry-run`
- `scripts/tibiahub-ops.sh db revision`
- `scripts/tibiahub-ops.sh db revision current`
- `scripts/tibiahub-ops.sh db revision heads`
- `scripts/tibiahub-ops.sh db revision history`
- `scripts/tibiahub-ops.sh db revision check`
- `scripts/tibiahub-ops.sh spatial verify --dry-run`
- `scripts/tibiahub-ops.sh deploy preflight --dry-run`

## 6) Commands that change production

- `db migrate`
- `db restore`
- `db reset`
- `db provision`
- `spatial rebuild --execute`
- `services restart`
- `admin bootstrap`
- `secrets generate`
- `deploy run`
- `deploy rollback`

## 7) Exact confirmation flag for every destructive operation

- deploy: `--confirm-deploy-tibiahub`
- rollback: `--confirm-rollback-tibiahub`
- migrate: `--confirm-migrate-tibiahub`
- restore: `--confirm-restore-tibiahub`
- reset: `--confirm-reset-tibiahub`
- provision: `--confirm-provision-tibiahub`
- spatial rebuild execute: `--confirm-rebuild-spatial-links`
- services restart: `--confirm-restart-tibiahub`
- admin bootstrap: `--confirm-bootstrap-admin`
- secrets generate: `--confirm-generate-secrets`

## 8) Exact dry-run support

- `scripts/tibiahub-ops.sh deploy preflight --dry-run`
- `scripts/tibiahub-ops.sh db migrate --dry-run`
- `scripts/tibiahub-ops.sh db restore --dry-run /absolute/path/to/backup.dump`
- `scripts/tibiahub-ops.sh db reset --dry-run`
- `scripts/tibiahub-ops.sh db provision --dry-run`
- `scripts/tibiahub-ops.sh services restart --dry-run tibiahub-api`
- `scripts/tibiahub-ops.sh spatial rebuild --dry-run`
- `scripts/tibiahub-ops.sh secrets generate --dry-run`

Dry-run prints the command it would run and must not mutate PM2, PostgreSQL data, deployment state, Git state, frontend dist, or secret files.

## 9) System status and health checks

```bash
scripts/tibiahub-ops.sh status
scripts/tibiahub-ops.sh health
scripts/tibiahub-ops.sh diagnose
```

## 10) PM2 service status, logs, restart

```bash
scripts/tibiahub-ops.sh services status
scripts/tibiahub-ops.sh services logs tibiahub-api
scripts/tibiahub-ops.sh services restart --confirm-restart-tibiahub tibiahub-api
scripts/tibiahub-ops.sh services restart --dry-run tibiahub-api
```

## 11) PostgreSQL status and verification

```bash
scripts/tibiahub-ops.sh db status
scripts/tibiahub-ops.sh db verify --dry-run
```

## 12) Alembic current/heads/history/check

```bash
scripts/tibiahub-ops.sh db revision
scripts/tibiahub-ops.sh db revision current
scripts/tibiahub-ops.sh db revision heads
scripts/tibiahub-ops.sh db revision history
scripts/tibiahub-ops.sh db revision check
```

Rules:

- `db revision` defaults to `current`.
- only `current|heads|history|check` are accepted.
- unknown or extra arguments fail with non-zero.

## 13) Database migration

```bash
scripts/tibiahub-ops.sh db migrate --confirm-migrate-tibiahub
scripts/tibiahub-ops.sh db migrate --dry-run
```

## 14) Backup

```bash
scripts/tibiahub-ops.sh db backup
scripts/tibiahub-ops.sh db backup /var/backups/tibiahub/manual.dump
```

## 15) Restore

```bash
scripts/tibiahub-ops.sh db restore --confirm-restore-tibiahub /var/backups/tibiahub/tibiahub-TIMESTAMP.dump
scripts/tibiahub-ops.sh db restore --dry-run /var/backups/tibiahub/tibiahub-TIMESTAMP.dump
```

## 16) Reset

```bash
scripts/tibiahub-ops.sh db reset --confirm-reset-tibiahub
scripts/tibiahub-ops.sh db reset --dry-run
```

## 17) Provisioning

```bash
scripts/tibiahub-ops.sh db provision --confirm-provision-tibiahub
scripts/tibiahub-ops.sh db provision --dry-run
```

## 18) PostGIS/spatial verification and rebuild

```bash
scripts/tibiahub-ops.sh spatial verify --dry-run
scripts/tibiahub-ops.sh spatial rebuild --dry-run
scripts/tibiahub-ops.sh spatial rebuild --execute --confirm-rebuild-spatial-links
```

## 19) Admin bootstrap

```bash
scripts/tibiahub-ops.sh admin bootstrap --confirm-bootstrap-admin
```

## 20) Secret verification and generation

```bash
scripts/tibiahub-ops.sh secrets verify
scripts/tibiahub-ops.sh secrets generate --confirm-generate-secrets
scripts/tibiahub-ops.sh secrets generate --dry-run
```

## 21) Deploy preflight

```bash
scripts/tibiahub-ops.sh deploy preflight --dry-run
```

## 22) Production deploy

```bash
scripts/tibiahub-ops.sh deploy run --confirm-deploy-tibiahub --previous-commit <sha40>
```

## 23) Rollback

```bash
scripts/tibiahub-ops.sh deploy rollback --confirm-rollback-tibiahub /forge/tibiahub-backups/deployments/<evidence-dir>
```

## 24) Deployment evidence structure

Typical evidence content under `/forge/tibiahub-backups/deployments/<timestamp-commit>/`:

- `metadata.env`
- `tibiahub.dump`
- `tibiahub.dump.sha256`
- `tibiahub.dump.list`
- `tibiahub.restore.list`
- `pm2-state.json`
- `pm2-state.tsv`
- `steps/`

## 25) FAILED and per-step logs

Deployment failures write `FAILED` with fields including failed step and step log file paths. Rollback failures write `ROLLBACK_FAILED_INFO`.

Per-step files:

- `steps/<step>.out.log`
- `steps/<step>.err.log`
- `steps/<step>.meta.env`

## 26) Media concurrency test

```bash
scripts/tibiahub-ops.sh media test --item-id <id>
scripts/tibiahub-ops.sh media test --item-id <id> --concurrency 50 --base-url http://127.0.0.1:8001
```

## 27) Common troubleshooting scenarios

- Unknown command or wrong arguments:
  - run `scripts/tibiahub-ops.sh help` and use the exact syntax.
- Confirmation errors:
  - pass the exact operation-specific flag; near matches are rejected.
- Deploy preflight failure:
  - inspect evidence `steps/*.err.log` and `FAILED` metadata paths.
- Alembic read-only command fails:
  - check stderr output and verify runtime secret/config permissions.

## 28) Recommended workflow before any destructive operation

1. Run `scripts/tibiahub-ops.sh status`.
2. Run `scripts/tibiahub-ops.sh health`.
3. Run `scripts/tibiahub-ops.sh db verify --dry-run`.
4. Run operation-specific dry-run if available.
5. Ensure backup/evidence path is ready.
6. Execute confirmed command once reviewed.

## 29) Commands that must never be executed casually

- `scripts/tibiahub-ops.sh db reset --confirm-reset-tibiahub`
- `scripts/tibiahub-ops.sh db restore --confirm-restore-tibiahub ...`
- `scripts/tibiahub-ops.sh db migrate --confirm-migrate-tibiahub`
- `scripts/tibiahub-ops.sh deploy run --confirm-deploy-tibiahub ...`
- `scripts/tibiahub-ops.sh deploy rollback --confirm-rollback-tibiahub ...`

## 30) Quick reference

```bash
# read-only checks
scripts/tibiahub-ops.sh status
scripts/tibiahub-ops.sh health
scripts/tibiahub-ops.sh db verify --dry-run
scripts/tibiahub-ops.sh db revision heads

# dry-run destructive paths
scripts/tibiahub-ops.sh db migrate --dry-run
scripts/tibiahub-ops.sh db restore --dry-run /path/to/backup.dump
scripts/tibiahub-ops.sh db reset --dry-run
scripts/tibiahub-ops.sh db provision --dry-run
scripts/tibiahub-ops.sh services restart --dry-run tibiahub-api
scripts/tibiahub-ops.sh spatial rebuild --dry-run
scripts/tibiahub-ops.sh secrets generate --dry-run
scripts/tibiahub-ops.sh deploy preflight --dry-run

# confirmed destructive paths
scripts/tibiahub-ops.sh db migrate --confirm-migrate-tibiahub
scripts/tibiahub-ops.sh db restore --confirm-restore-tibiahub /path/to/backup.dump
scripts/tibiahub-ops.sh db reset --confirm-reset-tibiahub
scripts/tibiahub-ops.sh db provision --confirm-provision-tibiahub
scripts/tibiahub-ops.sh services restart --confirm-restart-tibiahub tibiahub-api
scripts/tibiahub-ops.sh spatial rebuild --execute --confirm-rebuild-spatial-links
scripts/tibiahub-ops.sh admin bootstrap --confirm-bootstrap-admin
scripts/tibiahub-ops.sh secrets generate --confirm-generate-secrets
scripts/tibiahub-ops.sh deploy run --confirm-deploy-tibiahub --previous-commit <sha40>
scripts/tibiahub-ops.sh deploy rollback --confirm-rollback-tibiahub /forge/tibiahub-backups/deployments/<evidence-dir>
```
