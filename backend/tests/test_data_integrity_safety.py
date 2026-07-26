from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models.auth_security import AuthOneTimeToken
from app.models.character_ownership import CharacterOwnershipClaim
from scripts.audit_data_integrity import build_report
from tests.conftest import make_user


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_data_integrity.py"


def test_cleanup_cli_defaults_to_dry_run_and_rejects_incomplete_mutation_flags():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "delete(" not in source.lower()
    environment = os.environ.copy()
    result = subprocess.run(
        [str(ROOT / "backend" / "venv" / "bin" / "python"), str(SCRIPT), "--apply"],
        cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 2 and "Refusing mutation" in result.stderr
    relative = subprocess.run(
        [
            str(ROOT / "backend" / "venv" / "bin" / "python"), str(SCRIPT), "--apply",
            "--confirm", "APPLY-REVIEWED-NONDESTRUCTIVE-REPAIR",
            "--backup-output", "relative.dump",
        ],
        cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    assert relative.returncode == 2 and "absolute" in relative.stderr


def test_integrity_report_detects_stale_security_rows_without_mutating(db):
    admin = make_user(db, username="integrity-admin", is_superuser=True)
    expired = datetime.now(UTC) - timedelta(minutes=1)
    db.add(AuthOneTimeToken(
        user_id=admin.id, purpose="password_reset", token_hash="a" * 64,
        expires_at=expired,
    ))
    db.add(CharacterOwnershipClaim(
        user_id=admin.id, character_name="Stale Knight", normalized_name="stale knight",
        challenge_hash="b" * 64, status="pending", expires_at=expired,
    ))
    db.flush()
    report = build_report(db)
    assert report["mode"] == "dry-run"
    assert report["safety"] == {"active_global_admins": 1, "final_active_admin_preserved": True}
    assert report["stale"] == {"auth_tokens": 1, "ownership_claims": 1}
    assert report["mutation_plan"]["deletions"] == 0
    assert db.query(AuthOneTimeToken).one().invalidated_at is None
    assert db.query(CharacterOwnershipClaim).one().status == "pending"
