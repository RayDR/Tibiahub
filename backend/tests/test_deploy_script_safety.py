from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy" / "deploy.sh"
ROLLBACK = ROOT / "scripts" / "deploy" / "rollback.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deploy_script_has_required_safety_contracts():
    deploy = _text(DEPLOY)
    assert "set -Eeuo pipefail" in deploy
    assert "flock" in deploy
    assert "trap" in deploy
    assert "EXIT" in deploy
    assert "git status --porcelain" in deploy
    assert "backup" in deploy.lower()
    assert "alembic" in deploy.lower()
    assert "health" in deploy.lower()
    assert "rollback" in deploy.lower()


def test_rollback_script_has_required_safety_contracts():
    rollback = _text(ROLLBACK)
    assert "set -Eeuo pipefail" in rollback
    assert "flock" in rollback
    assert "alembic" in rollback.lower()
    assert "health" in rollback.lower()
    assert "runtime-current" in rollback


def test_deploy_preflight_happens_before_services_stop():
    deploy = _text(DEPLOY)
    assert deploy.index("010-preflight") < deploy.index("200-stop-services")


def test_deploy_schema_upgrade_happens_before_services_start():
    deploy = _text(DEPLOY)
    assert deploy.index("210-alembic-upgrade") < deploy.index("300-start-services")


def test_deploy_runs_health_check_after_services_start():
    deploy = _text(DEPLOY)
    assert deploy.index("300-start-services") < deploy.index("400-health-check")


def test_deploy_failure_path_invokes_rollback():
    deploy = _text(DEPLOY)
    assert "rollback" in deploy
    assert "rollback.sh" in deploy


def test_deploy_does_not_print_database_credentials():
    deploy = _text(DEPLOY)
    lower = deploy.lower()
    assert "echo $database_url" not in lower
    assert "echo \"$database_url\"" not in lower
    assert "set -x" not in lower


def test_postgres_helper_uses_external_secrets():
    postgres = _text(ROOT / "scripts" / "lib" / "postgres.sh")
    assert "TIBIAHUB_SECRETS_FILE" in postgres or "tibiahub-secrets" in postgres
    assert "DATABASE_URL" in postgres


def test_ecosystem_uses_external_runtime_secrets():
    ecosystem = _text(ROOT / "ecosystem.config.js")
    assert "TIBIAHUB_SECRETS_FILE" in ecosystem
    assert "/forge/tibiahub-secrets/runtime.env" in ecosystem
    assert "DATABASE_URL" not in ecosystem
    assert "OPENAI_API_KEY" not in ecosystem


def test_backend_runtime_is_versioned_activated_and_rollback_safe():
    deploy = _text(DEPLOY)
    rollback = _text(ROLLBACK)
    ecosystem = _text(
        ROOT / "ecosystem.config.js"
    )
    postgres = _text(
        ROOT / "scripts" / "lib" / "postgres.sh"
    )
    requirements = _text(
        ROOT / "backend" / "requirements.txt"
    )

    assert "TIBIAHUB_RUNTIME_ROOT" in deploy
    assert "015-preflight-backend-runtime" in deploy
    assert "python3 -m venv" in deploy
    assert "pip check" in deploy
    assert ".requirements.sha256" in deploy
    assert "205-activate-backend-runtime" in deploy
    assert "previous_runtime" in deploy

    assert (
        deploy.index("015-preflight-backend-runtime")
        < deploy.index("200-stop-services")
    )
    assert (
        deploy.index("200-stop-services")
        < deploy.index("205-activate-backend-runtime")
        < deploy.index("210-alembic-upgrade")
    )

    assert "045-restore-backend-runtime" in rollback
    assert "previous_runtime" in rollback
    assert "runtime-current" in rollback

    # API plus raffle, knowledge, email, sync, and localization workers all use
    # the same versioned backend runtime. Keep this count explicit so adding a
    # process requires updating the deployment safety contract deliberately.
    assert (
        ecosystem.count(
            "script: 'runtime-current/bin/python'"
        )
        == 6
    )

    assert "tibiahub_runtime_dir" in postgres
    assert "TIBIAHUB_PYTHON_RUNTIME" in postgres
    assert "runtime-current/bin/python" in postgres

    assert "PyJWT[crypto]==2.13.0" in requirements
    assert "python-jose" not in requirements
