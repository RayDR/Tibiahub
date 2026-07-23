from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.core.secrets import runtime_secrets_file, validate_secret_file


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "generate-tibiahub-secrets.sh"


def secure_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "tibiahub-secrets"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def test_runtime_secret_path_must_be_absolute(monkeypatch):
    monkeypatch.setenv("TIBIAHUB_SECRETS_FILE", "relative/runtime.env")
    with pytest.raises(RuntimeError, match="absolute"):
        runtime_secrets_file()


def test_secret_file_requires_owner_only_permissions(tmp_path):
    directory = secure_directory(tmp_path)
    secret_file = directory / "runtime.env"
    secret_file.write_text("APP_ENV='test'\n", encoding="utf-8")
    secret_file.chmod(0o640)
    with pytest.raises(RuntimeError, match="group or other"):
        validate_secret_file(secret_file, required=True)
    secret_file.chmod(0o600)
    assert validate_secret_file(secret_file, required=True) == secret_file


def test_secret_file_rejects_symlink_and_shared_directory(tmp_path):
    directory = secure_directory(tmp_path)
    secret_file = directory / "runtime.env"
    secret_file.write_text("APP_ENV='test'\n", encoding="utf-8")
    secret_file.chmod(0o600)
    link = directory / "runtime-link.env"
    link.symlink_to(secret_file)
    with pytest.raises(RuntimeError, match="regular file"):
        validate_secret_file(link, required=True)
    directory.chmod(0o750)
    with pytest.raises(RuntimeError, match="directory"):
        validate_secret_file(secret_file, required=True)


def test_generator_creates_external_owner_only_files_without_secret_output(tmp_path):
    secret_directory = tmp_path / "generated-secrets"
    environment = os.environ.copy()
    environment["TIBIAHUB_SECRETS_DIR"] = str(secret_directory)
    result = subprocess.run(
        [str(GENERATOR), "--confirm-create-tibiahub-secrets"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert stat.S_IMODE(secret_directory.stat().st_mode) == 0o700
    files = {name: secret_directory / name for name in ("runtime.env", "provision.env", "bootstrap.env")}
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files.values())
    runtime_text = files["runtime.env"].read_text(encoding="utf-8")
    provision_text = files["provision.env"].read_text(encoding="utf-8")
    bootstrap_text = files["bootstrap.env"].read_text(encoding="utf-8")
    assert "DATABASE_URL=" in runtime_text and "SECRET_KEY=" in runtime_text
    assert "PGUSER=''" in provision_text and "PGPASSWORD=''" in provision_text
    assert "TIBIAHUB_DB_PASSWORD=" in provision_text
    assert "BOOTSTRAP_ADMIN_PASSWORD=" in bootstrap_text
    for secret_value in (
        runtime_text.split("SECRET_KEY='", 1)[1].split("'", 1)[0],
        provision_text.split("TIBIAHUB_DB_PASSWORD='", 1)[1].split("'", 1)[0],
        bootstrap_text.split("BOOTSTRAP_ADMIN_PASSWORD='", 1)[1].split("'", 1)[0],
    ):
        assert secret_value not in result.stdout


def test_production_settings_load_external_secret_file(tmp_path):
    directory = secure_directory(tmp_path)
    secret_file = directory / "runtime.env"
    secret_file.write_text(
        "APP_ENV='production'\n"
        "DATABASE_URL='postgresql+psycopg2://tibiahub_app@127.0.0.1:5432/tibiahub'\n"
        "SECRET_KEY='test-only-value-with-at-least-32-characters'\n",
        encoding="utf-8",
    )
    secret_file.chmod(0o600)
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    environment.pop("APP_ENV", None)
    environment["TIBIAHUB_SECRETS_FILE"] = str(secret_file)
    result = subprocess.run(
        [str(ROOT / "backend" / "venv" / "bin" / "python"), "-c", "from app.core.config import settings; print(settings.database_name)"],
        cwd=ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "tibiahub"
