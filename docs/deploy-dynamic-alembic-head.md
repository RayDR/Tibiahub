# Dynamic Alembic deploy target

The guarded deploy resolves the release Alembic target from the migration graph at runtime.

- Deploy requires exactly one Alembic head.
- The resolved revision is reused for upgrade-path validation, deployment metadata, post-upgrade verification, and deployment state.
- Multiple heads or an invalid revision identifier stop the deploy during preflight before services are touched.
- Do not hardcode the latest revision in `deploy/scripts/deploy.sh` when adding migrations.
