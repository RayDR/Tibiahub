# TibiaHub operations script inventory

This inventory documents the final operational script scope, why each file is retained, and what was intentionally left unchanged.

## Consolidated architecture

- Human operational entrypoint: `scripts/tibiahub-ops.sh`
- Shared libraries: `scripts/lib/ops-common.sh`, `scripts/lib/postgres.sh`
- Independent deployment safety boundaries: `deploy/scripts/deploy.sh`, `deploy/scripts/rollback.sh`

## Script counts (merge-base vs current)

Merge-base (`git merge-base HEAD origin/develop`): `b822817e9d0ed344dde6280bf9ce421762ab3d4c`

- Root `*.sh`: before 3, after 3
- `scripts/*.sh`: before 11, after 12
- `deploy/scripts/*.sh`: before 2, after 2
- `backend/scripts/*`: before 0, after 0
- `frontend/scripts/*`: before 4, after 4

Result: no net reduction in tracked shell-script count; one consolidated entrypoint was added.

## Files retained

| File | Role | Status | Reason retained |
| --- | --- | --- | --- |
| `scripts/tibiahub-ops.sh` | Consolidated operations CLI | retained | Primary user-facing operational interface |
| `scripts/lib/ops-common.sh` | Shared logging/step/failure helpers | retained | Common library for deploy/rollback/CLI |
| `scripts/lib/postgres.sh` | Shared PostgreSQL/Alembic helpers | retained | Common safety and DB/Alembic behavior |
| `deploy/scripts/deploy.sh` | Guarded deployment entrypoint | retained | Independent safety boundary; must remain directly invokable |
| `deploy/scripts/rollback.sh` | Guarded rollback entrypoint | retained | Independent safety boundary; must remain directly invokable |
| `scripts/backup-postgres.sh` | Backup implementation script | retained | Called by CLI and `scripts/audit_data_integrity.py`; external usage possible |
| `scripts/restore-postgres.sh` | Restore implementation script | retained | Called by CLI and referenced in docs/tests; destructive safety contract preserved |
| `scripts/reset-postgres.sh` | Reset implementation script | retained | Called by CLI and covered by tests |
| `scripts/provision-postgres.sh` | Provision implementation script | retained (specialized) | Specialized flow with admin-mode checks; avoids monolithic CLI |
| `scripts/generate-tibiahub-secrets.sh` | Secrets generation implementation | retained (specialized) | Dedicated secrets lifecycle; tested and referenced externally |
| `scripts/verify-postgres.sh` | PostgreSQL verification | retained | Used by CLI, `start.sh`, and `info.sh` |
| `scripts/verify-postgis.sh` | PostGIS verification | retained | Safe read-only specialized check |
| `scripts/verify-spatial-consistency.sh` | Spatial consistency check | retained | Safe read-only specialized check |
| `scripts/rebuild-spatial-links.sh` | Spatial rebuild wrapper | retained | Provides operation-specific confirmation contract |
| `scripts/bootstrap-admin.sh` | Admin bootstrap wrapper | retained | Guarded bootstrap entrypoint from secure secret file |

## Compatibility wrappers retained

| File | Why kept |
| --- | --- |
| `scripts/postgres-common.sh` | Retained as a thin compatibility shim for unknown external callers; repository wrappers now source `scripts/lib/postgres.sh` directly |

## Files deleted

- None.

No operational or deployment safety scripts were deleted in this completion pass.

## Specialized implementation scripts retained

- `scripts/provision-postgres.sh`
- `scripts/generate-tibiahub-secrets.sh`

These were intentionally retained as standalone implementations because combining them into the CLI would increase blast radius and reduce maintainability.

## Python jobs intentionally left unchanged

The following Python jobs were not merged into Bash and were intentionally left unchanged:

- `scripts/audit_data_integrity.py`
- `scripts/audit_users.py`
- `scripts/bootstrap_admin.py`
- `scripts/bootstrap_test_users.py`
- `scripts/enqueue-knowledge-job.py`
- `scripts/ensure_admin_user.py`
- `scripts/postgres-command.py`
- `scripts/postgres-target.py`
- `scripts/rebuild-knowledge-relationships.py`
- `scripts/rebuild-spatial-links.py`
- `scripts/recover-expired-knowledge-jobs.py`
- `scripts/recover_admin.py`
- `scripts/resolve-knowledge-reference.py`
- `scripts/run_full_sync.py`
- `scripts/validate_original_scope.py`
- `scripts/verify-knowledge-graph.py`
- `scripts/verify-knowledge-worker.py`

## External usage audit summary

- Repository callers, docs, and tests were scanned for each legacy shell script.
- Readable user/system cron and readable systemd units were inspected.
- No tibiahub references were found in readable system cron or systemd units.
- Because external invocation outside the repository cannot be fully proven absent, thin wrappers were retained where appropriate.
