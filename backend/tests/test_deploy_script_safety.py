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


def test_deployment_scripts_are_valid_bash_and_expose_guarded_operator_cli():
    for script in (DEPLOY, ROLLBACK, OPS):
        assert script.stat().st_mode & 0o111
        assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0

    help_result = subprocess.run(
        [str(OPS), "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    rollback_result = subprocess.run(
        [str(ROLLBACK)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_result.returncode == 0
    assert "deploy [--confirm-deploy]" in help_result.stdout
    assert "deploy dry-run" in help_result.stdout
    assert "deploy status" in help_result.stdout
    assert "deploy history" in help_result.stdout
    assert "deploy rollback" in help_result.stdout
    assert "only bypasses the non-standard branch approval guard" in help_result.stdout
    assert "deploy run --confirm-deploy-tibiahub" not in help_result.stdout

    # The low-level rollback remains intentionally confirmation-gated because
    # it restores the database as well as runtime/frontend state. The operator
    # wrapper provides either an interactive prompt or --confirm-rollback.
    assert rollback_result.returncode == 2
    assert "--confirm-rollback" in rollback_result.stderr


def test_deploy_requires_lock_clean_remote_parity_branch_policy_and_expected_head():
    script = _text(DEPLOY)
    for required in (
        "flock -n",
        'target_branch="$(git branch --show-current)"',
        "git status --porcelain --untracked-files=all",
        'git fetch --quiet origin "$target_branch"',
        'refs/remotes/origin/$target_branch',
        'target_commit" == "$remote_commit',
        "resolve_default_branch",
        "branch_is_standard",
        "approve_nonstandard_branch",
        '[[ "$branch" == develop ]]',
        '[[ "$branch" == main || "$branch" == master ]]',
        "--confirm-deploy",
        'EXPECTED_REVISION=""',
        "migration_heads",
        'EXPECTED_REVISION="${migration_heads[0]}"',
        "require_local_tibiahub_target",
        "TIBIAHUB_DATABASE_NAME=tibiahub",
        "run_alembic_read_only check",
    ):
        assert required in script

    # --confirm-deploy is deliberately narrow: it only approves a
    # non-standard branch. It must not disable the clean-tree, remote-parity,
    # database, migration, or health checks above.
    assert "Non-standard branch guard bypassed with --confirm-deploy" in script
    assert "detached HEAD is not deployable" in script


def test_snapshot_frontend_pm2_health_and_rollback_guards_are_present():
    deploy = _text(DEPLOY)
    rollback = _text(ROLLBACK)
    for required in (
        "refs/tibiahub/deploy-snapshots/",
        'git update-ref "$commit_snapshot_ref" "$previous_commit"',
        "previous-commit.snapshot",
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
        "target_branch",
        "previous_branch",
        "previous_commit_ref",
    ):
        assert required in deploy
    for required in (
        "sha256sum --check --status",
        'pg_restore --list "$snapshot"',
        "--clean --if-exists --single-transaction --exit-on-error --no-owner --no-acl",
        '--dbname="$database_name"',
        '--use-list="$restore_list"',
        "previous_commit_ref",
        'git rev-parse --verify "$previous_commit_ref^{commit}"',
        "checkout_previous_commit",
        'git switch --detach "$previous_commit"',
        "frontend-dist-previous",
        "pm2-state.tsv",
    ):
        assert required in rollback
    assert "alembic downgrade" not in rollback.lower()
    assert "postgres_admin_dropdb" not in rollback
    assert "postgres_admin_createdb" not in rollback


def test_operator_rollback_resolves_current_snapshot_and_keeps_explicit_history_option():
    ops = _text(OPS)
    readme = _text(README)

    assert "deploy_rollback" in ops
    assert 'snapshot_dir" {print $2}' in ops
    assert 'evidence="$root_dir/$evidence"' in ops
    assert "--confirm-rollback" in ops
    assert "Continue with rollback? [y/N]" in ops
    assert "deploy history" in ops

    assert "scripts/tibiahub-ops.sh deploy rollback" in readme
    assert "protected Git ref" in readme
    assert "--previous-commit <sha40>" in readme
    assert "bootstrap/recovery" in readme


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
