from datetime import UTC, datetime, timedelta

from app.core.security import create_access_token
from app.models.maintenance_sync import SyncJobPhase
from app.services.sync_error_service import record_sync_error, sanitize_url
from app.services.sync_service import SyncService
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def make_failed_job(db, admin):
    job = SyncService.create_job(
        db, job_type="full", requester=admin.username, requested_by_user_id=admin.id,
        operation_label="Error diagnostics test",
    )
    phase = db.query(SyncJobPhase).filter_by(job_id=job.id, phase_key="images").one()
    phase.status = "failed"
    phase.processed_count = 100
    phase.failed_count = 96
    phase.finished_at = datetime.now(UTC)
    job.status = "completed_with_errors"
    db.commit()
    return job, phase


def test_phase_error_endpoint_is_admin_only_and_sanitizes_aggregates(db, client):
    admin = make_user(db, username="diagnostic_admin", is_superuser=True)
    member = make_user(db, username="diagnostic_member")
    job, phase = make_failed_job(db, admin)
    secret_url = "https://tibia.fandom.com/wiki/Special:FilePath/Test.gif?token=secret#private"
    first = record_sync_error(
        db, job_id=job.id, phase_key="images", entity_type="item", external_id="42",
        entity_name="Test item", category="provider_forbidden",
        provider="tibiawiki", source_url=secret_url, http_status=403,
        retryable=False, checkpoint_offset=7, attempt=1,
    )
    first.last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
    record_sync_error(
        db, job_id=job.id, phase_key="images", entity_type="item", external_id="42",
        entity_name="Test item", category="provider_forbidden",
        provider="tibiawiki", source_url=secret_url, http_status=403,
        retryable=False, checkpoint_offset=8, attempt=2,
    )
    record_sync_error(
        db, job_id=job.id, phase_key="images", entity_type="creature", external_id="99",
        entity_name="Newest creature", category="provider_timeout",
        provider="static.wikia.nocookie.net", source_url="https://static.wikia.nocookie.net/tibia/new.webp?x=y",
        retryable=True, checkpoint_offset=9, attempt=1,
    )
    db.commit()

    path = f"/api/v1/admin/sync/jobs/{job.id}/phases/images/errors"
    assert client.get(path, headers=auth(member)).status_code == 403
    response = client.get(path, headers=auth(admin), params={"limit": 1, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_error_records"] == 2
    assert payload["total_affected_entities"] == 2
    assert payload["rows"][0]["entity_name"] == "Newest creature"
    assert "?" not in payload["rows"][0]["url"] and "#" not in payload["rows"][0]["url"]
    assert "secret" not in response.text

    filtered = client.get(path, headers=auth(admin), params={"http_status": 403, "retryable": False, "search": "Test"}).json()
    assert filtered["total_error_records"] == 1
    assert filtered["rows"][0]["occurrence_count"] == 2
    assert filtered["rows"][0]["url"] == "https://tibia.fandom.com/wiki/Special:FilePath/Test.gif"

    job_payload = client.get(f"/api/v1/admin/sync/jobs/{job.id}", headers=auth(admin)).json()
    image_phase = next(row for row in job_payload["phases"] if row["phase_key"] == "images")
    assert image_phase["last_error"]["entity_name"] == "Newest creature"
    assert image_phase["last_error"]["affected_count"] == 2
    assert phase.failed_count / phase.processed_count > 0.8


def test_historical_phase_error_and_url_sanitizer(db, client):
    admin = make_user(db, username="historical_diagnostic_admin", is_superuser=True)
    job, _phase = make_failed_job(db, admin)
    response = client.get(
        f"/api/v1/admin/sync/jobs/{job.id}/phases/images/errors", headers=auth(admin),
    )
    assert response.status_code == 200
    assert response.json()["historical_message"] == "Detailed information was not recorded for this earlier failure."
    assert sanitize_url("https://user:pass@example.com/path?token=x") == "https://example.com/path"
    assert sanitize_url("http://example.com/image.png") is None
