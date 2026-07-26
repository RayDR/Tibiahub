#!/usr/bin/env python3
"""Report TibiaHub data conflicts; optionally apply bounded, backed-up repairs.

Dry-run is unconditional unless all of --apply, the exact confirmation phrase,
and an absolute backup output path are supplied. The repair mode never deletes
domain data or changes users, permissions, guilds, raffles, or ownership history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.models.auth_security import AuthOneTimeToken  # noqa: E402
from app.models.character_ownership import CharacterOwnershipClaim  # noqa: E402
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_character import UserCharacter  # noqa: E402

CONFIRMATION = "APPLY-REVIEWED-NONDESTRUCTIVE-REPAIR"


def _duplicates(db, model, column) -> list[dict]:
    normalized = func.lower(func.trim(column))
    rows = db.query(normalized.label("value"), func.count(model.id)).filter(column.isnot(None)).group_by(normalized).having(func.count(model.id) > 1).all()
    return [{"normalized_value": value, "count": count} for value, count in rows]


def build_report(db) -> dict:
    now = datetime.now(UTC)
    active_admins = db.query(User).filter(User.is_superuser.is_(True), User.is_active.is_(True)).count()
    verified_conflicts = db.query(UserCharacter.normalized_name, func.count(UserCharacter.id)).filter(
        UserCharacter.ownership_status == "verified",
    ).group_by(UserCharacter.normalized_name).having(func.count(UserCharacter.id) > 1).all()
    orphan_participants = db.query(RaffleParticipant.id).outerjoin(Raffle, Raffle.id == RaffleParticipant.raffle_id).filter(Raffle.id.is_(None)).count()
    orphan_prizes = db.query(RafflePrize.id).outerjoin(Raffle, Raffle.id == RafflePrize.raffle_id).filter(Raffle.id.is_(None)).count()
    orphan_winners = db.query(RaffleWinner.id).outerjoin(Raffle, Raffle.id == RaffleWinner.raffle_id).filter(Raffle.id.is_(None)).count()
    stale_tokens = db.query(AuthOneTimeToken.id).filter(
        AuthOneTimeToken.expires_at <= now,
        AuthOneTimeToken.consumed_at.is_(None),
        AuthOneTimeToken.invalidated_at.is_(None),
    ).count()
    stale_claims = db.query(CharacterOwnershipClaim.id).filter(
        CharacterOwnershipClaim.expires_at <= now,
        CharacterOwnershipClaim.status.in_(["pending", "queued", "processing"]),
    ).count()
    legacy_characters = db.query(UserCharacter.id).filter(UserCharacter.ownership_status == "legacy_unverified").count()
    return {
        "mode": "dry-run",
        "generated_at": now.isoformat(),
        "safety": {"active_global_admins": active_admins, "final_active_admin_preserved": active_admins >= 1},
        "duplicates": {
            "usernames_casefolded": _duplicates(db, User, User.username),
            "emails_casefolded": _duplicates(db, User, User.email),
            "character_names_casefolded": _duplicates(db, UserCharacter, UserCharacter.character_name),
        },
        "conflicts": {
            "verified_character_owners": [{"normalized_name": name, "count": count} for name, count in verified_conflicts],
            "legacy_unverified_characters": legacy_characters,
        },
        "orphans": {"raffle_participants": orphan_participants, "raffle_prizes": orphan_prizes, "raffle_winners": orphan_winners},
        "stale": {"auth_tokens": stale_tokens, "ownership_claims": stale_claims},
        "mutation_plan": {
            "invalidate_expired_auth_tokens": stale_tokens,
            "expire_stale_ownership_claims": stale_claims,
            "deletions": 0,
            "user_or_permission_changes": 0,
        },
    }


def _backup(output: Path) -> None:
    if not output.is_absolute():
        raise ValueError("Backup output must be an absolute path")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(PROJECT_ROOT / "scripts" / "backup-postgres.sh"), str(output)], cwd=PROJECT_ROOT, check=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("PostgreSQL backup was not created")


def apply_bounded_repairs(db) -> dict:
    now = datetime.now(UTC)
    invalidated = db.query(AuthOneTimeToken).filter(
        AuthOneTimeToken.expires_at <= now,
        AuthOneTimeToken.consumed_at.is_(None),
        AuthOneTimeToken.invalidated_at.is_(None),
    ).update({AuthOneTimeToken.invalidated_at: now}, synchronize_session=False)
    expired = db.query(CharacterOwnershipClaim).filter(
        CharacterOwnershipClaim.expires_at <= now,
        CharacterOwnershipClaim.status.in_(["pending", "queued", "processing"]),
    ).update({CharacterOwnershipClaim.status: "expired", CharacterOwnershipClaim.consumed_at: now, CharacterOwnershipClaim.lease_expires_at: None}, synchronize_session=False)
    db.commit()
    return {"invalidated_expired_auth_tokens": invalidated, "expired_ownership_claims": expired, "deletions": 0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TibiaHub duplicates, conflicts, orphans, and stale security data")
    parser.add_argument("--apply", action="store_true", help="Apply only the bounded stale-token/claim updates")
    parser.add_argument("--confirm", help=f"Required exact phrase: {CONFIRMATION}")
    parser.add_argument("--backup-output", type=Path, help="Absolute path for the mandatory pre-mutation PostgreSQL backup")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and (
        args.confirm != CONFIRMATION
        or args.backup_output is None
        or not args.backup_output.is_absolute()
    ):
        print("Refusing mutation: exact --confirm and an absolute --backup-output are required", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        report = build_report(db)
        if args.apply:
            if report["safety"]["active_global_admins"] < 1:
                print("Refusing mutation: no active global administrator exists", file=sys.stderr)
                return 2
            _backup(args.backup_output)
            report["mode"] = "apply"
            report["backup"] = str(args.backup_output)
            report["applied"] = apply_bounded_repairs(db)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"[{'APPLY' if args.apply else 'DRY-RUN'}] TibiaHub data integrity report")
            for section in ("safety", "duplicates", "conflicts", "orphans", "stale", "mutation_plan"):
                print(f"{section}={json.dumps(report[section], sort_keys=True)}")
            if args.apply:
                print(f"applied={json.dumps(report['applied'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
