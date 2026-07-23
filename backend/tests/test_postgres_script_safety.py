from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "scripts" / "reset-postgres.sh"


def run_reset(*args: str, environment: dict[str, str] | None = None):
    return subprocess.run(
        [str(RESET), *args],
        cwd=ROOT,
        env=environment or os.environ.copy(),
        capture_output=True,
        text=True,
    )


def test_reset_requires_exact_confirmation_flag():
    assert run_reset().returncode == 2
    assert run_reset("--yes").returncode == 2
    assert run_reset("--confirm-reset-tibiahub", "extra").returncode == 2


def test_reset_refuses_wildcard_database_target():
    environment = os.environ.copy()
    environment.update(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg2://unused@127.0.0.1:5432/tibiahub_test",
        TIBIAHUB_DATABASE_NAME="*",
    )
    result = run_reset("--confirm-reset-tibiahub", environment=environment)
    assert result.returncode == 2
    assert "wildcard" in result.stderr.lower()


def test_reset_refuses_database_name_mismatch_before_admin_access():
    environment = os.environ.copy()
    environment.update(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg2://unused@127.0.0.1:5432/not_tibiahub_test",
        TIBIAHUB_DATABASE_NAME="tibiahub_test",
    )
    result = run_reset("--confirm-reset-tibiahub", environment=environment)
    assert result.returncode == 2
    assert "does not match" in result.stderr.lower()
