# Guarded TibiaHub deployment

`deploy/scripts/deploy.sh` is the only supported production deployment entry
point. It refuses to run unless the checkout is a clean `develop` exactly equal
to `origin/develop`, the database is local PostgreSQL named `tibiahub`, and the
repository has the expected single Alembic head.

The workflow acquires a deployment lock, loads credentials only from the
existing external secure environment, creates and validates a mode-0600 custom
PostgreSQL snapshot, records Git and Alembic metadata, creates an
extension-preserving restore catalog, backs up `frontend/dist`,
and captures sanitized PM2 state. Because validation can already have rebuilt
the ignored live `dist`, it also checks out the recorded previous commit in a
temporary Git worktree and creates a reproducible previous-commit frontend
build for rollback. It builds the target frontend into the evidence directory
before stopping only these applications:

- `tibiahub-api`
- `tibiahub-frontend`
- `tibiahub-raffle-scheduler`
- `tibiahub-knowledge-worker`
- `tibiahub-email-worker`

It then migrates, installs the staged frontend build, starts or reloads only
those services, and requires all local and public health checks to pass. Any
failure after services are stopped invokes snapshot-based rollback; Alembic
downgrade is never used. Evidence is retained whether deployment succeeds or
fails.

## Deploy

For the first guarded deployment, supply the commit currently running in
production. Later deployments read it from the external deployment state:

```bash
deploy/scripts/deploy.sh --confirm-deploy-tibiahub \
  --previous-commit <40-character-deployed-commit>
```

Evidence and state default to `/forge/tibiahub-backups/deployments`. Override
that location only with `TIBIAHUB_DEPLOY_ROOT` pointing to a secure external
directory owned by the deployment user.

## Manual rollback

Use the exact evidence directory printed by deployment:

```bash
deploy/scripts/rollback.sh --confirm-rollback-tibiahub \
  /forge/tibiahub-backups/deployments/<deployment-directory>
```

Rollback verifies the snapshot checksum and catalog, stops only TibiaHub PM2
applications, restores the prior Git commit, and transactionally cleans and
restores application-role-owned objects in only the local `tibiahub` database.
Administrator-owned PostgreSQL extensions remain intact, and Alembic downgrade
is never used. It then restores the prior frontend build and PM2 states and
retains all evidence for investigation.
