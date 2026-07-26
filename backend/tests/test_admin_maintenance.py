from datetime import UTC, datetime

import pytest

from app.models.user_character import UserCharacter
from app.services.admin_maintenance_service import AdminMaintenanceService, MaintenanceError
from tests.conftest import make_raffle, make_user


def test_final_active_admin_is_never_deactivatable(db):
    admin = make_user(db, username="maintenance_admin", is_superuser=True)
    report = AdminMaintenanceService.preflight(db, "users", str(admin.id))

    assert report["deletable"] is False
    assert "final_global_admin" in report["blockers"]
    with pytest.raises(MaintenanceError):
        AdminMaintenanceService.execute(db, admin, "users", str(admin.id), admin.username, "Requested retirement")


def test_raffle_maintenance_is_soft_delete_and_audited(db):
    admin = make_user(db, username="raffle_maintenance_admin", is_superuser=True)
    raffle = make_raffle(db, creator_id=admin.id)
    report = AdminMaintenanceService.preflight(db, "raffles", str(raffle.id))

    result = AdminMaintenanceService.execute(db, admin, "raffles", str(raffle.id), report["confirmation"], "Obsolete development raffle")
    db.flush()

    assert result["executed"] is True
    assert raffle.is_deleted is True
    assert raffle.status == "deleted"
    assert db.query(type(raffle)).filter_by(id=raffle.id).count() == 1


def test_only_legacy_character_without_claim_can_be_unlinked(db):
    admin = make_user(db, username="character_maintenance_admin", is_superuser=True)
    owner = make_user(db, username="character_owner")
    verified = UserCharacter(
        user_id=owner.id, character_name="Verified Owner", normalized_name="verified owner",
        ownership_status="verified", ownership_verified_at=datetime.now(UTC),
    )
    legacy = UserCharacter(
        user_id=owner.id, character_name="Legacy Link", normalized_name="legacy link",
        ownership_status="legacy_unverified",
    )
    db.add_all([verified, legacy]); db.flush()

    assert AdminMaintenanceService.preflight(db, "characters", str(verified.id))["deletable"] is False
    report = AdminMaintenanceService.preflight(db, "characters", str(legacy.id))
    AdminMaintenanceService.execute(db, admin, "characters", str(legacy.id), "Legacy Link", "Remove obsolete legacy link")
    db.flush()

    assert report["deletable"] is True
    assert db.get(UserCharacter, legacy.id) is None


def test_confirmation_and_reason_are_rechecked_server_side(db):
    admin = make_user(db, username="confirmation_admin", is_superuser=True)
    user = make_user(db, username="maintenance_target")

    with pytest.raises(MaintenanceError, match="Confirmation"):
        AdminMaintenanceService.execute(db, admin, "users", str(user.id), "wrong", "Valid audited reason")
    with pytest.raises(MaintenanceError, match="reason"):
        AdminMaintenanceService.execute(db, admin, "users", str(user.id), user.username, "no")
