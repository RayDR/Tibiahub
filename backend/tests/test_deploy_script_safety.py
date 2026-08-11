from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "scripts" / "deploy.sh"
ROLLBACK = ROOT / "deploy" / "scripts" / "rollback.sh"
OPS = ROOT / "scripts" / "tibiahub-ops.sh"
README = ROOT / "deploy" / "README.md"
ALLOWED_SERVICES = {
    "tibiahub-api",
    "tibiahub-frontend",
    "tibiahub-raffle-scheduler",
    "tibiahub-knowledge-worker",
    "tibiahub-email-worker",
    "tibiahub-sync-worker",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deployment_scripts_are_valid_bash_and_require_exact_confirmation():
    for script in (DEPLOY, ROLLBACK):
        assert script.stat().st_mode & 0o111
        assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0

    deploy_result = subprocess.run([str(DEPLOY)], cwd=ROOT, capture_output=True, text=True)
    rollback_result = subprocess.run([str(ROLLBACK)], cwd=ROOT, capture_output=True, text=True)
    assert deploy_result.returncode == 2
    assert rollback_result.returncode == 2
    assert "--confirm-deploy-tibiahub" in deploy_result.stderr
    assert "--confirm-rollback-tibiahub" in rollback_result.stderr


def test_deploy_requires_lock_clean_exact_develop_and_expected_head():
    script = _text(DEPLOY)
    for required in (
        "flock -n",
        'git branch --show-current)" == "develop"',
        "git status --porcelain --untracked-files=all",
        "refs/remotes/origin/develop",
        'target_commit" == "$remote_commit',
        'EXPECTED_REVISION="sync_errors_20260803"',
        "migration_heads",
        "require_local_tibiahub_target",
        "TIBIAHUB_DATABASE_NAME=tibiahub",
        "run_alembic_read_only check",
    ):
        assert required in script
    assert "master" not in script.lower()


def test_snapshot_frontend_pm2_health_and_rollback_guards_are_present():
    deploy = _text(DEPLOY)
    rollback = _text(ROLLBACK)
    for required in (
        "pg_dump --format=custom",
        'chmod 600 "$snapshot"',
        'pg_restore --list "$snapshot"',
        'sha256sum "$snapshot"',
        "tibiahub.restore.list",
        "TABLE DATA public spatial_ref_sys",
        'cp -a "$ROOT/frontend/dist"',
        'git worktree add --quiet --detach "$previous_worktree" "$previous_commit"',
        "frontend-dist-previous",
        "pm2-state.json",
        "rollback_armed=1",
        "ROLLBACK_SUCCEEDED",
        "ROLLBACK_FAILED",
        "http://127.0.0.1:8001/api/v1/health",
        "https://tibiahub.domoforge.com/api/v1/ready",
        "email_worker_heartbeats",
        "knowledge_worker_heartbeats",
        "raffle_scheduler_state",
        "sync_worker_heartbeats",
    ):
        assert required in deploy
    for required in (
        "sha256sum --check --status",
        'pg_restore --list "$snapshot"',
        "--clean --if-exists --single-transaction --exit-on-error --no-owner --no-acl",
        '--dbname="$database_name"',
        '--use-list="$restore_list"',
        'git switch --detach "$previous_commit"',
        "frontend-dist-previous",
        "pm2-state.tsv",
    ):
        assert required in rollback
    assert "alembic downgrade" not in rollback.lower()
    assert "postgres_admin_dropdb" not in rollback
    assert "postgres_admin_createdb" not in rollback


def test_pm2_operations_are_bounded_to_the_declared_tibiahub_services():
    combined = _text(DEPLOY) + _text(ROLLBACK)
    declared = {
        line.strip()
        for line in combined.splitlines()
        if line.strip().startswith("tibiahub-")
    }
    assert declared == ALLOWED_SERVICES
    for forbidden in ("pm2 restart all", "pm2 stop all", "pm2 delete all", "pm2 kill"):
        assert forbidden not in combined
    assert combined.count("env -i") == 2

    # Service definitions must be recreated rather than reloaded so PM2
    # cannot retain a stale executable path across runtime migrations.
    assert "startOrReload" not in combined
    assert (
        combined.count(
            'pm2 start "$ROOT/ecosystem.config.js" --only "$service"'
        )
        == 2
    )
    assert combined.count('pm2 delete "$service"') >= 2


def test_entrypoints_refuse_being_sourced():
    for script in (DEPLOY, ROLLBACK, OPS):
        text = _text(script)
        assert '[[ "${BASH_SOURCE[0]}" != "$0" ]]' in text
        assert "must be executed, not sourced" in text


def test_scripts_do_not_embed_or_print_database_credentials():
    combined = _text(DEPLOY) + _text(ROLLBACK) + _text(README)
    assert "set -x" not in combined
    assert "TEST_DATABASE_URL" not in combined
    assert "postgresql://" not in combined
    assert 'echo "$DATABASE_URL"' not in combined
    assert 'printf "%s" "$DATABASE_URL"' not in combined
    assert "PGPASSWORD=" not in combined
    assert "cat $TIBIAHUB" not in combined
    assert "/forge/tibiahub-secrets/runtime.env" not in combined



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

    assert (
        ecosystem.count(
            "script: 'runtime-current/bin/python'"
        )
        == 5
    )

    assert "tibiahub_runtime_dir" in postgres
    assert "TIBIAHUB_PYTHON_RUNTIME" in postgres
    assert "runtime-current/bin/python" in postgres

    assert "PyJWT[crypto]==2.13.0" in requirements
    assert "python-jose" not in requirements
