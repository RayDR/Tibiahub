# Archived SQLite utilities

These scripts are retained only as historical references for the unpublished
SQLite prototype. They are not supported runtime, migration, deployment, or
recovery paths. Do not run them against PostgreSQL.

The active schema starts at the PostgreSQL Alembic baseline in
`backend/alembic/versions/`. Existing SQLite data is intentionally not migrated
in Stage 1.
