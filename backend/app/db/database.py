"""PostgreSQL engine, sessions, and migration-state verification."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import BACKEND_ROOT, Settings, settings


logger = logging.getLogger("app.database")
ALEMBIC_CONFIG_PATH = BACKEND_ROOT / "alembic.ini"


class DatabaseNotReadyError(RuntimeError):
    """Safe startup error that contains no host, SQL, or credentials."""


def _engine_options(config: Settings, url: URL) -> dict[str, Any]:
    common: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": config.DATABASE_POOL_RECYCLE_SECONDS,
    }
    if url.get_backend_name() == "postgresql":
        common.update(
            pool_size=config.DATABASE_POOL_SIZE,
            max_overflow=config.DATABASE_MAX_OVERFLOW,
            pool_timeout=config.DATABASE_POOL_TIMEOUT_SECONDS,
            connect_args={
                "connect_timeout": config.DATABASE_CONNECT_TIMEOUT_SECONDS,
                "options": (
                    "-c timezone=UTC "
                    f"-c statement_timeout={config.DATABASE_STATEMENT_TIMEOUT_MS} "
                    f"-c idle_in_transaction_session_timeout={config.DATABASE_IDLE_TRANSACTION_TIMEOUT_MS}"
                ),
            },
        )
    elif config.APP_ENV == "test" and url.get_backend_name() == "sqlite":
        common["connect_args"] = {"check_same_thread": False}
    return common


def create_database_engine(
    config: Settings = settings,
    *,
    url: URL | str | None = None,
    **overrides: Any,
) -> Engine:
    """Build an engine from the shared configuration path."""
    engine_url = make_url(url) if isinstance(url, str) else (url or config.database_url)
    options = _engine_options(config, engine_url)
    if "poolclass" in overrides:
        options.pop("pool_size", None)
        options.pop("max_overflow", None)
        options.pop("pool_timeout", None)
    options.update(overrides)
    return create_engine(engine_url, **options)


engine = create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logger.info(
    "database_configured dialect=%s database=%s",
    settings.database_url.get_backend_name(),
    settings.database_name,
)


def get_db():
    """FastAPI dependency for one database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def expected_schema_revision() -> str:
    """Pin the deploy's expected head at process startup/first readiness check."""
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise DatabaseNotReadyError("database migration head is not configured")
    return head


def current_schema_revision(connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def verify_connection_and_schema(target_engine: Engine = engine) -> None:
    """Fail safely unless PostgreSQL is reachable and exactly at Alembic head."""
    dialect = target_engine.url.get_backend_name()
    if dialect != "postgresql":
        if settings.APP_ENV == "test" and dialect == "sqlite":
            return
        raise DatabaseNotReadyError("configured database is not PostgreSQL")
    try:
        with target_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = current_schema_revision(connection)
    except Exception as exc:
        raise DatabaseNotReadyError("database is unavailable") from exc
    if current != expected_schema_revision():
        raise DatabaseNotReadyError("database schema is missing or outdated; run Alembic upgrade head")


def readiness_status(target) -> tuple[bool, str]:
    """Return a public-safe readiness result for an existing connection."""
    try:
        connection_factory = getattr(target, "connection", None)
        connection = connection_factory() if callable(connection_factory) else target
        connection.execute(text("SELECT 1"))
        if connection.dialect.name != "postgresql":
            if settings.APP_ENV == "test" and connection.dialect.name == "sqlite":
                return True, "ok"
            return False, "invalid_database"
        if current_schema_revision(connection) != expected_schema_revision():
            return False, "schema_mismatch"
    except Exception:
        return False, "unavailable"
    return True, "ok"
