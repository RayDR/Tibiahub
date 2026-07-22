# PostgreSQL foundation operations

TibiaHub supports PostgreSQL 16+ as its sole development and production runtime database. SQLite remains only in isolated unit tests and archived prototype utilities. The API and scheduler never create or alter tables at startup; Alembic is the schema authority.

## Architecture and scope

- Database: `tibiahub`
- Application role: `tibiahub_app`
- Connectivity: localhost only (`127.0.0.1`, `localhost`, or `::1`)
- Credentials: `backend/.env` or process environment, never source control
- Required extensions: `pg_trgm`, `unaccent`
- Optional Stage 1 extension: `postgis`
- Deferred: pgvector, PostGIS domain models, Redis, S3, new search, and sync redesign

On Ubuntu with PostgreSQL 16, install PostGIS later with `postgresql-16-postgis-3` if `pg_available_extensions` does not list `postgis`. Its absence does not block Stage 1.

## Configuration

Copy `backend/.env.example` to `backend/.env`, replace every placeholder, and keep the file mode restricted. `DATABASE_URL` has no default. Outside `APP_ENV=test`, a non-PostgreSQL URL is rejected immediately.

The API, raffle scheduler, Alembic, bootstrap command, and operational scripts all load this same backend configuration without depending on process cwd. Database logs include only dialect and database name, never host or credentials.

## Provision a new local database

Provisioning requires an elevated local PostgreSQL URL and a password supplied only through the environment. The script refuses alternate database or role names and does not edit another database or PostgreSQL's global configuration. Confirm separately that `listen_addresses` and firewall policy do not expose port 5432 publicly.

```bash
cd /forge/tibiahub
export POSTGRES_ADMIN_URL='postgresql:///postgres'
export TIBIAHUB_DB_PASSWORD='replace-with-a-generated-secret'
./scripts/provision-postgres.sh --confirm-provision-tibiahub
unset TIBIAHUB_DB_PASSWORD POSTGRES_ADMIN_URL
```

Set the matching application URL in `backend/.env`, then apply the schema:

```bash
cd /forge/tibiahub/backend
venv/bin/alembic -c alembic.ini upgrade head
venv/bin/alembic -c alembic.ini current
```

The clean baseline creates every currently supported table from an empty database. It installs `pg_trgm` and `unaccent`; it installs PostGIS when the server package and privileges are available.

## Optional initial administrator

No account is created implicitly. Supply all three values for one explicit run:

```bash
cd /forge/tibiahub
export BOOTSTRAP_ADMIN_USERNAME='initial-admin'
export BOOTSTRAP_ADMIN_EMAIL='admin@example.invalid'
export BOOTSTRAP_ADMIN_PASSWORD='replace-with-a-generated-secret'
PYTHONPATH=backend backend/venv/bin/python scripts/bootstrap_admin.py
unset BOOTSTRAP_ADMIN_USERNAME BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_PASSWORD
```

## Exact deployment sequence

1. Confirm PostgreSQL 16+ is available only on localhost.
2. Preserve the previous runtime file outside the repository, if it exists: `install -m 600 backend/tibia_bestiary.db /var/backups/tibiahub/tibia_bestiary-pre-postgres.db`. Do not delete the original automatically.
3. Run `scripts/provision-postgres.sh --confirm-provision-tibiahub` with explicit elevated credentials.
4. Put the application `DATABASE_URL` and secrets in `backend/.env`.
5. Run `cd backend && venv/bin/alembic -c alembic.ini upgrade head` exactly once.
6. Optionally run the explicit bootstrap-admin command above.
7. Start only the API: `pm2 start ecosystem.config.js --only tibiahub-api`.
8. Require HTTP 200 from `http://127.0.0.1:8001/api/v1/ready`.
9. Start `tibiahub-raffle-scheduler`, then build/restart the frontend.

`./start.sh` performs steps 7-9 only after database verification. It never runs Alembic. PM2 uses absolute working directories, and both Python processes read the same `backend/.env`.

## Backup, restore, reset, and verify

Backups use PostgreSQL custom format and default to `/var/backups/tibiahub`:

```bash
./scripts/backup-postgres.sh
./scripts/verify-postgres.sh
```

Restore is destructive within the configured TibiaHub database and requires an exact confirmation plus an explicit file:

```bash
./scripts/restore-postgres.sh --confirm-restore-tibiahub /var/backups/tibiahub/tibiahub-TIMESTAMP.dump
```

A full reset is never automatic. It validates the local dialect and exact database name, can stop only TibiaHub API/scheduler processes, preserves a legacy SQLite copy when present, recreates only the configured TibiaHub database, and applies Alembic head:

```bash
export POSTGRES_ADMIN_URL='postgresql:///postgres'
export STOP_TIBIAHUB_SERVICES=1
./scripts/reset-postgres.sh --confirm-reset-tibiahub
```

## Startup and readiness

API and scheduler startup verify connectivity and exact Alembic head. A missing or outdated schema terminates startup with a credential-free message. `/healthz` is liveness only; `/ready` checks connectivity and migration revision and returns HTTP 503 with a safe reason when unavailable or mismatched. No process automatically migrates, calls `create_all`, or executes runtime `ALTER TABLE`.

The scheduler claims due raffles in a short transaction using PostgreSQL `FOR UPDATE SKIP LOCKED`, a unique job ID, and the existing bounded retry/lease state. Multiple workers cannot successfully claim the same raffle.

## Tests

Unit tests explicitly use SQLite in memory. PostgreSQL integration tests require a disposable database whose name contains `test`; they refuse `tibiahub` or an ambiguous name.

```bash
export TEST_DATABASE_URL='postgresql+psycopg2://tibiahub_test_app:secret@127.0.0.1:5432/tibiahub_test'
backend/venv/bin/python -m pytest backend/tests -q
```

The integration fixture destroys only the public schema in that clearly named test database, upgrades from empty to Alembic head, exercises application flows, and truncates its own tables between tests.

## Rollback

1. Stop `tibiahub-raffle-scheduler`, then `tibiahub-api`.
2. Back up the failed state with `scripts/backup-postgres.sh` if it may aid diagnosis.
3. Restore the last known-good custom dump with the explicit restore command.
4. Check out the matching application release and run its documented Alembic target; never stamp a revision to hide a mismatch.
5. Run `scripts/verify-postgres.sh`, start the API, confirm `/ready`, then start the scheduler and frontend.

The old SQLite files are preservation artifacts, not an automatic runtime rollback path. Provider/Cyclopedia content may be rebuilt in the next sync stage; Stage 1 intentionally contains no general SQLite-to-PostgreSQL ETL.
