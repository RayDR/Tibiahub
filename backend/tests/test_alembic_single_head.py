from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_alembic_has_single_head():
    backend_root = _backend_root()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    heads = ScriptDirectory.from_config(config).get_heads()

    # The database migration invariant requires exactly one head to avoid branch divergences
    assert len(heads) == 1, f"Expected a single migration head, found: {heads}"


def test_hunt_zone_registry_migration_quotes_reserved_symmetric_identifier():
    migration = (
        _backend_root() / "alembic" / "versions" / "hunt_zone_registry_20260815.py"
    ).read_text()

    assert '\n                "symmetric",' in migration
    assert '"symmetric" = EXCLUDED."symmetric"' in migration
