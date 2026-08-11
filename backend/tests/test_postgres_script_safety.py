from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "scripts" / "reset-postgres.sh"
PROVISION = ROOT / "scripts" / "provision-postgres.sh"
ECOSYSTEM = ROOT / "ecosystem.config.js"


def run_reset(*args: str, environment: dict[str, str] | None = None):
    env = (environment or os.environ.copy()).copy()
    env.setdefault(
        "TIBIAHUB_PYTHON_RUNTIME",
        sys.prefix,
    )

    return subprocess.run(
        [str(RESET), *args],
        cwd=ROOT,
        env=env,
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


def test_postgres_scripts_do_not_put_credentials_in_command_arguments():
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROVISION, RESET, ROOT / "scripts" / "backup-postgres.sh", ROOT / "scripts" / "restore-postgres.sh", ROOT / "scripts" / "verify-postgres.sh")
    )
    assert "POSTGRES_ADMIN_URL" not in scripts
    assert "libpq_url" not in scripts
    assert 'role_password="$TIBIAHUB_DB_PASSWORD"' not in scripts
    assert "-v role_password" not in scripts
    assert "\\set role_password" in PROVISION.read_text(encoding="utf-8")


def test_peer_admin_mode_uses_non_interactive_sudo_without_fallback():
    common = (ROOT / "scripts" / "lib" / "postgres.sh").read_text(encoding="utf-8")
    assert "sudo -n -u postgres psql" in common
    assert "no fallback was attempted" in common
    assert 'TIBIAHUB_POSTGRES_ADMIN_MODE:-}" == "peer"' in common


def test_pm2_configuration_contains_only_the_non_secret_file_path():
    ecosystem = ECOSYSTEM.read_text(encoding="utf-8")
    assert "TIBIAHUB_SECRETS_FILE" in ecosystem
    assert "DATABASE_URL" not in ecosystem
    assert "PGPASSWORD" not in ecosystem
    assert "SECRET_KEY" not in ecosystem


def test_wrappers_source_shared_postgres_library_directly():
    wrappers = [
        ROOT / "scripts" / "backup-postgres.sh",
        ROOT / "scripts" / "bootstrap-admin.sh",
        ROOT / "scripts" / "provision-postgres.sh",
        ROOT / "scripts" / "rebuild-spatial-links.sh",
        ROOT / "scripts" / "reset-postgres.sh",
        ROOT / "scripts" / "restore-postgres.sh",
        ROOT / "scripts" / "verify-postgis.sh",
        ROOT / "scripts" / "verify-postgres.sh",
        ROOT / "scripts" / "verify-spatial-consistency.sh",
    ]
    for wrapper in wrappers:
        text = wrapper.read_text(encoding="utf-8")
        assert "source \"$SCRIPT_DIR/lib/postgres.sh\"" in text
        assert "postgres-common.sh" not in text
