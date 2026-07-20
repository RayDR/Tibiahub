# PostgreSQL Migration Readiness (without migrating data yet)

This project supports connecting to SQLite or PostgreSQL through `DATABASE_URL`.
Existing PostgreSQL databases are **not** migrated by `create_all()` and must be
upgraded with the versioned Alembic migration before deploying the new code.

## 1) Set DATABASE_URL

Use one of these formats:

- SQLite:
  - `DATABASE_URL=sqlite:///./tibia_bestiary.db`
- PostgreSQL (recommended for runtime):
  - `DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/tibiahub`
- PostgreSQL async URL (accepted in env):
  - `DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/tibiahub`

Note: the backend currently uses SQLAlchemy sync engine. If `postgresql+asyncpg://` is provided, runtime normalizes to `postgresql+psycopg2://` automatically.

## 2) Install DB driver

Inside your backend virtualenv:

`psycopg2-binary` is pinned in `backend/requirements.txt` and is installed with
the normal backend dependencies.

Optional (for future async engine migration):

```bash
pip install asyncpg
```

## 3) Create PostgreSQL database

Example commands:

```bash
sudo -u postgres psql
CREATE DATABASE tibiahub;
CREATE USER tibiahub_user WITH PASSWORD 'change_me';
GRANT ALL PRIVILEGES ON DATABASE tibiahub TO tibiahub_user;
\q
```

Then set:

```bash
export DATABASE_URL='postgresql+psycopg2://tibiahub_user:change_me@127.0.0.1:5432/tibiahub'
```

## 4) Upgrade an existing database

Back up and test against a staging copy first, then run the checked-in Alembic
revision through the project's normal Alembic environment:

```bash
alembic upgrade product_polish_20260720
```

The migration only creates the new media table and adds missing nullable/defaulted
columns. Its downgrade is intentionally non-destructive.

## 5) Run app

Use your normal startup flow (PM2 or uvicorn). No data migration is performed automatically from SQLite to PostgreSQL yet.

## 6) Important dialect behavior

- SQLite-only PRAGMA and runtime `ALTER TABLE` auto-migrations run **only** when dialect is SQLite.
- PostgreSQL startup skips SQLite-specific migration logic.

## 7) Future migration notes

When ready to migrate real data from SQLite to PostgreSQL:

1. Freeze writes briefly (maintenance window).
2. Export SQLite data (or use one-time ETL script).
3. Import into PostgreSQL.
4. Validate counts and key relations (creatures, loot, quests, hunt_zones, media_assets).
5. Switch `DATABASE_URL` to PostgreSQL in production.
6. Keep SQLite backup until rollback window closes.

Do not treat `Base.metadata.create_all()` as a migration mechanism for an existing database.
