from __future__ import annotations

import os
import subprocess
from pathlib import Path

from sqlalchemy.pool import NullPool

from app.db import database


ROOT = Path(__file__).resolve().parents[2]


class DummySettings:
    APP_ENV = "production"
    DATABASE_POOL_RECYCLE_SECONDS = 120
    DATABASE_POOL_SIZE = 5
    DATABASE_MAX_OVERFLOW = 7
    DATABASE_POOL_TIMEOUT_SECONDS = 33
    DATABASE_CONNECT_TIMEOUT_SECONDS = 9
    DATABASE_STATEMENT_TIMEOUT_MS = 5000
    DATABASE_IDLE_TRANSACTION_TIMEOUT_MS = 2500


def test_queuepool_engine_receives_pool_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = str(url)
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    engine = database.create_database_engine(
        config=DummySettings(),
        url="postgresql+psycopg2://user:pass@127.0.0.1:5432/tibiahub",
    )

    assert engine is not None
    kwargs = captured["kwargs"]
    assert kwargs["pool_timeout"] == DummySettings.DATABASE_POOL_TIMEOUT_SECONDS
    assert kwargs["pool_size"] == DummySettings.DATABASE_POOL_SIZE
    assert kwargs["max_overflow"] == DummySettings.DATABASE_MAX_OVERFLOW
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == DummySettings.DATABASE_POOL_RECYCLE_SECONDS
    assert kwargs["connect_args"]["connect_timeout"] == DummySettings.DATABASE_CONNECT_TIMEOUT_SECONDS


def test_nullpool_engine_does_not_receive_pool_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = str(url)
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    engine = database.create_database_engine(
        config=DummySettings(),
        url="postgresql+psycopg2://user:pass@127.0.0.1:5432/tibiahub",
        poolclass=NullPool,
    )

    assert engine is not None
    kwargs = captured["kwargs"]
    assert "pool_timeout" not in kwargs
    assert "pool_size" not in kwargs
    assert "max_overflow" not in kwargs
    assert kwargs["poolclass"] is NullPool
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == DummySettings.DATABASE_POOL_RECYCLE_SECONDS
    assert kwargs["connect_args"]["connect_timeout"] == DummySettings.DATABASE_CONNECT_TIMEOUT_SECONDS


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_fake_alembic_tree(tmp_path: Path, *, fail_current: bool = False) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "repo"
    backend = root / "backend"
    alembic_bin = backend / "venv" / "bin"
    alembic_bin.mkdir(parents=True)
    (backend / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    # Runtime discovery now verifies the selected environment's Python before
    # resolving sibling commands such as Alembic. Model a complete runtime,
    # not only the command under test.
    _write_executable(alembic_bin / "python", "#!/usr/bin/env bash\nexit 0\n")

    _write_executable(
        alembic_bin / "alembic",
        """#!/usr/bin/env bash
set -euo pipefail
cmd="${3:-}"
if [[ "${MOCK_FAIL_CURRENT:-0}" == "1" && "$cmd" == "current" ]]; then
  printf 'simulated alembic failure\n' >&2
  exit 41
fi
case "$cmd" in
  heads|current|history|check)
    printf 'ok:%s\n' "$cmd"
    exit 0
    ;;
  *)
    printf 'unexpected command: %s\n' "$cmd" >&2
    exit 3
    ;;
esac
""",
    )

    runtime = tmp_path / "runtime.env"
    runtime.write_text("DATABASE_URL='postgresql+psycopg2://u:p@127.0.0.1:5432/tibiahub'\n", encoding="utf-8")
    runtime.chmod(0o600)

    env = os.environ.copy()
    env.update(
        {
            "MOCK_FAIL_CURRENT": "1" if fail_current else "0",
        }
    )
    return root, env


def test_read_only_alembic_commands_succeed_with_fake_runner(tmp_path: Path) -> None:
    root, env = _prepare_fake_alembic_tree(tmp_path)
    lib = ROOT / "scripts" / "lib" / "postgres.sh"
    runtime = tmp_path / "runtime.env"

    command = (
        f"source '{lib}' && "
        f"TIBIAHUB_ROOT='{root}' && "
        f"TIBIAHUB_BACKEND='{root / 'backend'}' && "
        f"TIBIAHUB_RUNTIME_SECRETS_FILE='{runtime}' && "
        "run_alembic_read_only heads && "
        "run_alembic_read_only current && "
        "run_alembic_read_only history && "
        "run_alembic_read_only check"
    )
    result = subprocess.run(["/usr/bin/bash", "-c", command], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "ok:heads" in result.stdout
    assert "ok:current" in result.stdout
    assert "ok:history" in result.stdout
    assert "ok:check" in result.stdout


def test_alembic_error_propagates_nonzero_and_stderr(tmp_path: Path) -> None:
    root, env = _prepare_fake_alembic_tree(tmp_path, fail_current=True)
    lib = ROOT / "scripts" / "lib" / "postgres.sh"
    runtime = tmp_path / "runtime.env"

    result = subprocess.run(
        [
            "/usr/bin/bash",
            "-c",
            (
                f"source '{lib}' && "
                f"TIBIAHUB_ROOT='{root}' && "
                f"TIBIAHUB_BACKEND='{root / 'backend'}' && "
                f"TIBIAHUB_RUNTIME_SECRETS_FILE='{runtime}' && "
                "run_alembic_read_only current"
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 41
    assert "simulated alembic failure" in result.stderr
