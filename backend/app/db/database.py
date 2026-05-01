"""Database configuration and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


SQLITE_RUNTIME_MIGRATIONS = {
    "creatures": {
        "normalized_name": "VARCHAR(150)",
        "slug": "VARCHAR(150)",
        "external_id": "VARCHAR(100)",
        "source_name": "VARCHAR(50)",
        "source_url": "VARCHAR(255)",
        "bestiary_class": "VARCHAR(100)",
        "bestiary_level": "VARCHAR(50)",
        "charm_points": "INTEGER",
        "creature_class": "VARCHAR(100)",
        "primary_type": "VARCHAR(100)",
        "data_sources": "TEXT",
        "missing_fields": "TEXT",
        "related_tasks": "TEXT",
        "locations": "TEXT",
        "raw_data": "TEXT",
        "last_synced_at": "DATETIME",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "loot": {
        "normalized_name": "VARCHAR(150)",
        "external_id": "VARCHAR(100)",
        "item_image_url": "VARCHAR(255)",
        "source_url": "VARCHAR(255)",
        "raw_data": "TEXT",
    },
    "hunt_zones": {
        "normalized_name": "VARCHAR(150)",
        "source_name": "VARCHAR(50)",
        "source_url": "VARCHAR(255)",
        "raw_data": "TEXT",
        "last_synced_at": "DATETIME",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "users": {
        "world_name": "VARCHAR(100)",
        "guild_name": "VARCHAR(200)",
        "residence": "VARCHAR(100)",
        "achievement_points": "INTEGER",
        "last_login_at": "DATETIME",
        "tibia_status": "VARCHAR(50)",
        "tibia_last_error": "VARCHAR(255)",
    },
    "user_characters": {
        "world_name": "VARCHAR(100)",
        "guild_name": "VARCHAR(200)",
        "guild_rank": "VARCHAR(100)",
        "residence": "VARCHAR(100)",
        "achievement_points": "INTEGER",
        "sex": "VARCHAR(20)",
        "last_login_at": "DATETIME",
    },
}

SQLITE_RUNTIME_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_creatures_normalized_name ON creatures(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_loot_normalized_name ON loot(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_hunt_zones_normalized_name ON hunt_zones(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_users_tibia_character_name ON users(tibia_character_name)",
)


def _run_sqlite_runtime_migrations():
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        for table_name, columns in SQLITE_RUNTIME_MIGRATIONS.items():
            try:
                existing = {
                    row[1]
                    for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
                }
            except Exception:
                continue

            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"
                )

        for statement in SQLITE_RUNTIME_INDEXES:
            connection.exec_driver_sql(statement)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    from app.models import (  # noqa: F401
        creature,
        entity_metadata,
        element,
        loot,
        spawn_location,
        hunt_zone,
        user,
        guild,
        user_character,
        events,
        external_data,
        raffle,
    )
    Base.metadata.create_all(bind=engine)
    _run_sqlite_runtime_migrations()
