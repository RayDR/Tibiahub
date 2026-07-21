"""Database configuration and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create database engine (sync SQLAlchemy engine for SQLite + PostgreSQL)
_db_url = make_url(settings.DATABASE_URL)
_db_dialect = _db_url.get_backend_name()
_is_sqlite = _db_dialect == "sqlite"

# SQLAlchemy sync engine cannot use asyncpg directly.
# If an asyncpg URL is provided, normalize it to psycopg2 for runtime compatibility.
if _db_dialect == "postgresql" and _db_url.drivername == "postgresql+asyncpg":
    _db_url = _db_url.set(drivername="postgresql+psycopg2")

_SQLITE_CONNECT_ARGS = {"check_same_thread": False, "timeout": 5} if _is_sqlite else {}
_ENGINE_KWARGS = {
    "pool_pre_ping": True,
}

engine = create_engine(
    _db_url,
    connect_args=_SQLITE_CONNECT_ARGS,
    **_ENGINE_KWARGS,
)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

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
        "classification": "VARCHAR(50)",
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
        # image alias/override support
        "image_alias": "VARCHAR(255)",
        "image_url_override": "VARCHAR(1024)",
        "image_source_name": "VARCHAR(255)",
                "image_locked": "BOOLEAN DEFAULT 0",
                "image_asset_id": "INTEGER",
        "is_hidden": "BOOLEAN DEFAULT 0",
        },
    "loot": {
        "normalized_name": "VARCHAR(150)",
        "external_id": "VARCHAR(100)",
        "item_image_url": "VARCHAR(255)",
        "item_image_alias": "VARCHAR(255)",
        "item_image_url_override": "VARCHAR(1024)",
        "item_image_locked": "BOOLEAN DEFAULT 0",
        "source_url": "VARCHAR(255)",
        "raw_data": "TEXT",
        "image_asset_id": "INTEGER",
    },
    "hunt_zones": {
        "normalized_name": "VARCHAR(150)",
        "slug": "VARCHAR(150)",
        "source_name": "VARCHAR(50)",
        "source_provider": "VARCHAR(50)",
        "source_url": "VARCHAR(255)",
        "region": "VARCHAR(100)",
        "recommended_vocations": "TEXT",
        "recommended_party_size": "VARCHAR(50)",
        "exp_rating": "VARCHAR(20)",
        "profit_rating": "VARCHAR(20)",
        "danger_rating": "VARCHAR(20)",
        "map_x": "INTEGER",
        "map_y": "INTEGER",
        "map_z": "INTEGER",
        "map_bounds": "TEXT",
        "raw_data": "TEXT",
        "map_asset_id": "INTEGER",
        "last_synced_at": "DATETIME",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "tibiawiki_quests": {
        "slug": "VARCHAR(180)",
        "source_url": "VARCHAR(1024)",
        "group_name": "VARCHAR(255)",
        "parent_page": "VARCHAR(255)",
        "rewards": "TEXT",
        "requirements": "TEXT",
        "related_creatures": "TEXT",
        "is_group": "BOOLEAN DEFAULT 0",
        "last_synced_at": "DATETIME",
    },
    "users": {
        "avatar_url": "VARCHAR(255)",
        "world_name": "VARCHAR(100)",
        "guild_name": "VARCHAR(200)",
        "residence": "VARCHAR(100)",
        "achievement_points": "INTEGER",
        "last_login_at": "DATETIME",
        "tibia_status": "VARCHAR(50)",
        "tibia_last_error": "VARCHAR(255)",
        "display_name": "VARCHAR(100)",
        "title": "VARCHAR(100)",
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
    "announcements": {
        "guild_name": "VARCHAR(200)",
        "deleted_at": "DATETIME",
        "deleted_by_user_id": "INTEGER",
        "delete_reason": "TEXT",
        "is_deleted": "BOOLEAN DEFAULT 0",
    },
    "guild_events": {
        "guild_name": "VARCHAR(200)",
        "deleted_at": "DATETIME",
        "deleted_by_user_id": "INTEGER",
        "delete_reason": "TEXT",
        "is_deleted": "BOOLEAN DEFAULT 0",
    },
    "events": {
        "public_code": "VARCHAR(6)",
        "registration_enabled": "BOOLEAN DEFAULT 1",
        "archive_after_days": "INTEGER DEFAULT 7",
        "archived_at": "DATETIME",
        "deleted_at": "DATETIME",
        "deleted_by_user_id": "INTEGER",
        "delete_reason": "TEXT",
        "is_deleted": "BOOLEAN DEFAULT 0",
    },
    "raffles": {
        "public_code": "VARCHAR(6)",
        "access_mode": "VARCHAR(20) DEFAULT 'guild_only'",
        "show_participants": "BOOLEAN DEFAULT 1",
        "visibility": "VARCHAR(20) DEFAULT 'public'",
        "registration_enabled": "BOOLEAN DEFAULT 1",
        "run_mode": "VARCHAR(20) DEFAULT 'manual'",
        "scheduled_run_at": "DATETIME",
        "archive_after_days": "INTEGER DEFAULT 7",
        "archived_at": "DATETIME",
        "deleted_at": "DATETIME",
        "deleted_by_user_id": "INTEGER",
        "delete_reason": "TEXT",
        "is_deleted": "BOOLEAN DEFAULT 0",
    },
    "raffle_participants": {
        "weight_multiplier": "FLOAT DEFAULT 1.0",
        "deleted_at": "DATETIME",
        "deleted_by_user_id": "INTEGER",
        "delete_reason": "TEXT",
        "is_deleted": "BOOLEAN DEFAULT 0",
    },
    "sync_jobs": {
        "progress_current": "INTEGER DEFAULT 0",
        "progress_total": "INTEGER DEFAULT 0",
        "progress_percent": "INTEGER DEFAULT 0",
        "current_step": "VARCHAR(255)",
        "message": "TEXT",
        "result_summary": "TEXT",
        "requester": "VARCHAR(255)",
        "job_limit": "INTEGER",
        "requested_by_user_id": "INTEGER",
        "error_message": "TEXT",
        "current_entity_type": "VARCHAR(50)",
        "current_offset": "INTEGER DEFAULT 0",
        "processed_count": "INTEGER DEFAULT 0",
        "failed_count": "INTEGER DEFAULT 0",
        "last_successful_external_id": "VARCHAR(255)",
        "checkpoint": "TEXT",
        "batch_size": "INTEGER DEFAULT 100",
        "max_retries": "INTEGER DEFAULT 3",
        "external_timeout_seconds": "INTEGER DEFAULT 15",
    },
    "cached_resources": {
        "resource_key": "VARCHAR(128)",
        "checksum": "VARCHAR(128)",
        "fetch_attempts": "INTEGER DEFAULT 0",
        "error_message": "TEXT",
    },
}

SQLITE_RUNTIME_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_creatures_name ON creatures(name)",
    "CREATE INDEX IF NOT EXISTS idx_creatures_normalized_name ON creatures(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_creatures_slug ON creatures(slug)",
    "CREATE INDEX IF NOT EXISTS idx_creatures_classification ON creatures(classification)",
    "CREATE INDEX IF NOT EXISTS idx_creatures_is_boss ON creatures(is_boss)",
    "CREATE INDEX IF NOT EXISTS idx_loot_item_name ON loot(item_name)",
    "CREATE INDEX IF NOT EXISTS idx_loot_normalized_name ON loot(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_hunt_zones_name ON hunt_zones(name)",
    "CREATE INDEX IF NOT EXISTS idx_hunt_zones_normalized_name ON hunt_zones(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_entity_metadata_entity_type ON entity_metadata(entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_entity_metadata_entity_key ON entity_metadata(entity_key)",
    "CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_activity_created_at ON user_activity(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_user_activity_user_id_created_at ON user_activity(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_users_tibia_character_name ON users(tibia_character_name)",
    "CREATE INDEX IF NOT EXISTS idx_announcements_is_deleted ON announcements(is_deleted)",
    "CREATE INDEX IF NOT EXISTS idx_guild_events_is_deleted ON guild_events(is_deleted)",
    "CREATE INDEX IF NOT EXISTS idx_events_is_deleted ON events(is_deleted)",
    "CREATE INDEX IF NOT EXISTS idx_raffles_is_deleted ON raffles(is_deleted)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_raffles_public_code ON raffles(public_code)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_public_code ON events(public_code)",
    "CREATE INDEX IF NOT EXISTS idx_sync_jobs_requested_by_user_id ON sync_jobs(requested_by_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sync_jobs_current_entity_type ON sync_jobs(current_entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_cached_resources_resource_key ON cached_resources(resource_key)",
    "CREATE INDEX IF NOT EXISTS idx_sync_job_errors_job_id ON sync_job_errors(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_sync_job_errors_entity_type ON sync_job_errors(entity_type)",
)


def _run_sqlite_runtime_migrations():
    if not _is_sqlite:
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
            try:
                connection.exec_driver_sql(statement)
            except Exception:
                # Some legacy databases may not include every optional table.
                continue

        # Backfill new guild scopes from each content author's current guild.
        for table_name in ("announcements", "guild_events"):
            try:
                connection.exec_driver_sql(
                    f"UPDATE {table_name} SET guild_name = "
                    f"(SELECT users.guild_name FROM users WHERE users.id = {table_name}.author_id) "
                    "WHERE guild_name IS NULL"
                )
            except Exception:
                continue


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
        guild_member_snapshot,
        settings,
        user_activity,
        media_asset,
    )
    Base.metadata.create_all(bind=engine)
    _run_sqlite_runtime_migrations()
