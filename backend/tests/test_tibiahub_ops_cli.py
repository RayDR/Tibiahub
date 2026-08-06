from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "tibiahub-ops.sh"
POSTGRES_COMMON = ROOT / "scripts" / "postgres-common.sh"
OPERATIONS_USER_GUIDE = ROOT / "docs" / "operations-user-guide.md"


def _run_ops(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/usr/bin/bash", str(OPS), *args],
        cwd=ROOT,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _mocked_env(tmp_path: Path, *, bash_exit: int = 0, bash_stderr: str = "") -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "mock.log"

    _write_executable(
        bin_dir / "bash",
                """#!/usr/bin/bash
set -euo pipefail
printf 'bash %s\n' "$*" >>"$MOCK_LOG"
if [[ -n "${MOCK_BASH_STDERR:-}" ]]; then
  printf '%s\n' "$MOCK_BASH_STDERR" >&2
fi
exit "${MOCK_BASH_EXIT:-0}"
""",
    )

    for name in ("pm2", "pg_restore", "psql", "alembic", "git", "rm", "mv", "cp"):
        _write_executable(
            bin_dir / name,
            f"""#!/usr/bin/bash
set -euo pipefail
printf '{name} %s\\n' \"$*\" >>\"$MOCK_LOG\"
exit 97
""",
        )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "MOCK_LOG": str(log_file),
            "MOCK_BASH_EXIT": str(bash_exit),
            "MOCK_BASH_STDERR": bash_stderr,
            "TIBIAHUB_DEPLOY_ROOT": str(tmp_path / "deploy-root"),
            "TIBIAHUB_SECRETS_DIR": str(tmp_path / "secrets"),
        }
    )
    (tmp_path / "deploy-root").mkdir()
    return env


def _mock_lines(log_file: Path) -> list[str]:
    if not log_file.exists():
        return []
    return [line.strip() for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_help_returns_success() -> None:
    result = _run_ops("help")
    assert result.returncode == 0
    assert "Usage: scripts/tibiahub-ops.sh" in result.stdout


def test_unknown_command_returns_nonzero_and_usage() -> None:
    result = _run_ops("nope")
    assert result.returncode != 0
    assert "Unknown command: nope" in result.stderr
    assert "Usage: scripts/tibiahub-ops.sh" in result.stdout


def test_production_changing_commands_require_exact_confirmation_flags() -> None:
    cases = [
        ["db", "migrate"],
        ["db", "restore", "/tmp/a.dump"],
        ["db", "reset"],
        ["services", "restart", "tibiahub-api"],
        ["spatial", "rebuild", "--execute"],
        ["secrets", "generate"],
        ["deploy", "run"],
        ["deploy", "rollback", "/tmp/evidence"],
    ]
    for args in cases:
        result = _run_ops(*args)
        assert result.returncode == 2


def test_wrong_confirmation_flag_is_rejected() -> None:
    result = _run_ops("db", "migrate", "--confirm-reset-tibiahub")
    assert result.returncode == 2
    assert "--confirm-migrate-tibiahub" in result.stderr


def test_dry_run_prints_commands_and_remains_read_only(tmp_path: Path) -> None:
    env = _mocked_env(tmp_path)
    deploy_state = Path(env["TIBIAHUB_DEPLOY_ROOT"]) / "current.env"
    deploy_state.write_text("deployed_commit=keep\n", encoding="utf-8")

    commands = [
        ["deploy", "preflight", "--dry-run"],
        ["db", "migrate", "--dry-run"],
        ["db", "restore", "--dry-run", "/tmp/backup with spaces.dump"],
        ["db", "reset", "--dry-run"],
        ["db", "provision", "--dry-run"],
        ["services", "restart", "--dry-run", "tibiahub-api"],
        ["spatial", "rebuild", "--dry-run"],
        ["secrets", "generate", "--dry-run"],
    ]

    outputs: list[str] = []
    for args in commands:
        result = _run_ops(*args, env=env)
        assert result.returncode == 0
        outputs.append(result.stdout + result.stderr)

    joined_output = "\n".join(outputs)
    assert "[dry-run]" in joined_output
    assert "backup\\ with\\ spaces.dump" in joined_output

    log_lines = _mock_lines(Path(env["MOCK_LOG"]))
    assert any("bash /forge/tibiahub/deploy/scripts/deploy.sh --dry-run" in line for line in log_lines)
    forbidden_prefixes = ("pm2 ", "pg_restore ", "psql ", "alembic ", "git ", "rm ", "mv ", "cp ")
    assert not any(line.startswith(forbidden_prefixes) for line in log_lines)

    assert deploy_state.read_text(encoding="utf-8") == "deployed_commit=keep\n"
    secrets_dir = Path(env["TIBIAHUB_SECRETS_DIR"])
    assert not secrets_dir.exists() or not any(secrets_dir.iterdir())


def test_sourced_execution_refuses_without_terminating_caller() -> None:
    result = subprocess.run(
        [
            "/usr/bin/bash",
            "-c",
            "set +e; source scripts/tibiahub-ops.sh; rc=$?; echo caller-still-running; exit $rc",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "caller-still-running" in result.stdout
    assert "must be executed, not sourced" in result.stderr


def test_child_process_status_and_stderr_are_propagated(tmp_path: Path) -> None:
    env = _mocked_env(tmp_path, bash_exit=23, bash_stderr="mock child failure")
    result = _run_ops("db", "verify", env=env)
    assert result.returncode == 23
    assert "mock child failure" in result.stderr


def test_wrapper_compatibility_shim_retained() -> None:
    assert POSTGRES_COMMON.exists()
    shim = POSTGRES_COMMON.read_text(encoding="utf-8")
    assert "Compatibility shim" in shim
    assert "scripts/lib/postgres.sh" in shim


def test_db_revision_unknown_and_extra_arguments_are_rejected() -> None:
    result = _run_ops("db", "revision", "unsupported")
    assert result.returncode == 2
    assert "Unknown db revision operation" in result.stderr

    result = _run_ops("db", "revision", "current", "extra")
    assert result.returncode == 2
    assert "Usage: db revision" in result.stderr


def test_db_revision_dispatch_contract_is_explicit() -> None:
    text = OPS.read_text(encoding="utf-8")
    assert 'local operation="${1:-current}"' in text
    assert 'run_alembic_read_only "$operation"' in text
    assert "current|heads|history|check" in text


def test_operations_user_guide_examples_match_supported_cli_syntax() -> None:
    guide = OPERATIONS_USER_GUIDE.read_text(encoding="utf-8")
    required_examples = [
        "scripts/tibiahub-ops.sh db revision",
        "scripts/tibiahub-ops.sh db revision current",
        "scripts/tibiahub-ops.sh db revision heads",
        "scripts/tibiahub-ops.sh db revision history",
        "scripts/tibiahub-ops.sh db revision check",
        "scripts/tibiahub-ops.sh db provision --dry-run",
        "scripts/tibiahub-ops.sh db provision --confirm-provision-tibiahub",
        "scripts/tibiahub-ops.sh services restart --dry-run",
        "scripts/tibiahub-ops.sh services restart --confirm-restart-tibiahub",
    ]
    for example in required_examples:
        assert example in guide
    assert "scripts/tibiahub-ops.sh db help" not in guide
    assert "scripts/tibiahub-ops.sh services help" not in guide
    assert "scripts/tibiahub-ops.sh deploy help" not in guide


def test_wrong_dry_run_usage_is_rejected() -> None:
    result = _run_ops("db", "restore", "--dry-run")
    assert result.returncode == 2
    assert "Usage: db restore" in result.stderr

    result = _run_ops("services", "restart", "--dry-run")
    assert result.returncode == 2
    assert "Usage: services restart" in result.stderr
