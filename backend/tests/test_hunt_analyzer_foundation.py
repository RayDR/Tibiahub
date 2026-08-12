from app.api.v1.endpoints.auth import get_current_admin_user, get_current_user
from app.models.hunt_analyzer import HuntAnalyzerSubmission
from app.models.user import User


def test_analyzer_samples_stay_pending_and_only_approved_samples_aggregate(client, db):
    from main import app
    user = User(username="analyzer-user", email="analyzer@example.test", hashed_password="test", is_active=True, is_superuser=False)
    admin = User(username="analyzer-admin", email="analyzer-admin@example.test", hashed_password="test", is_active=True, is_superuser=True)
    db.add_all([user, admin]); db.flush()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.post("/api/v1/hunt-analyzer/submissions", json={"payload": {"hunt_name": "Iksupan", "duration_seconds": 3600, "raw_exp": 1000000, "profit": 100000}})
        assert response.status_code == 200
        assert response.json() == {"id": response.json()["id"], "moderation_status": "pending", "authoritative": False}
        assert client.get("/api/v1/hunt-analyzer/aggregates", params={"zone": "Iksupan"}).json()["available"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    for raw_exp, profit in ((1000000, 100000), (1200000, 80000), (900000, 120000)):
        db.add(HuntAnalyzerSubmission(submitted_by_id=user.id, zone_name="Iksupan", normalized_zone="iksupan", duration_seconds=3600, raw_exp=raw_exp, profit=profit, source_kind="paste", source_payload={}, moderation_status="approved", moderated_by_id=admin.id))
    db.flush()
    aggregate = client.get("/api/v1/hunt-analyzer/aggregates", params={"zone": "Iksupan"}).json()
    assert aggregate["available"] is True and aggregate["sample_count"] == 3
    assert aggregate["raw_exp_per_hour"]["median"] == 1000000
    assert aggregate["profit_per_hour"]["q1"] <= aggregate["profit_per_hour"]["median"] <= aggregate["profit_per_hour"]["q3"]
    assert aggregate["authoritative"] is False

    app.dependency_overrides[get_current_admin_user] = lambda: admin
    try:
        pending_id = db.query(HuntAnalyzerSubmission).filter_by(moderation_status="pending").one().id
        moderated = client.patch(f"/api/v1/hunt-analyzer/submissions/{pending_id}/moderation", json={"status": "approved", "reason": "Validated against submitted screenshot"})
        assert moderated.status_code == 200 and moderated.json()["moderation_status"] == "approved"
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)


def test_analyzer_rejects_invalid_and_oversized_values(client, db):
    from main import app
    user = User(username="analyzer-invalid", email="invalid@example.test", hashed_password="test", is_active=True)
    db.add(user); db.flush(); app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.post("/api/v1/hunt-analyzer/submissions", json={"payload": {"hunt_name": "Iksupan", "duration_seconds": 1, "raw_exp": -1, "profit": 0}})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
