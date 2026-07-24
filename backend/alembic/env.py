from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.core.config import BACKEND_ROOT, settings
from app.db.database import Base, create_database_engine
import app.models  # noqa: F401


config = context.config
config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
config.set_main_option("sqlalchemy.url", settings.database_url.render_as_string(hide_password=False).replace("%", "%%"))
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name: str | None, type_: str, _parent_names: dict[str, str | None]) -> bool:
    """Ignore tables owned by installed PostgreSQL extensions."""
    return not (type_ == "table" and name == "spatial_ref_sys")


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_database_engine(poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
