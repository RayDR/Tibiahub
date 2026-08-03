from __future__ import annotations

import asyncio
import io
import json
import socket
from datetime import UTC, datetime

import httpx
import pytest
from PIL import Image

from app.core.security import create_access_token
from app.models.external_data import SyncJobError
from app.models.maintenance_sync import MaintenanceHold, SyncJobPhase
from app.models.media_asset import MediaAsset
from app.models.settings import SystemSettings
from app.services import media_asset_service as media
from app.services.sync_error_service import classify_exception
from app.services.sync_service import SyncService
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color=(30, 60, 90)).save(output, format="PNG")
    return output.getvalue()


def install_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    monkeypatch.setattr(media, "_validate_connected_peer", lambda _response: None)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])


def test_special_file_path_resolves_through_api_and_follows_allowed_redirect(monkeypatch):
    seen = []
    def handler(request: httpx.Request):
        seen.append((request.url.host, request.url.path))
        if request.url.host == "tibia.fandom.com":
            assert request.url.path == "/api.php"
            return httpx.Response(200, json={"query": {"pages": {"1": {"imageinfo": [{"url": "https://static.wikia.nocookie.net/tibia/redirect.webp?token=hidden"}]}}}})
        if request.url.path == "/tibia/redirect.webp":
            return httpx.Response(302, headers={"Location": "https://static.wikia.nocookie.net/tibia/final.png?signed=hidden"})
        return httpx.Response(200, content=png_bytes(), headers={"Content-Type": "image/png"})
    install_transport(monkeypatch, handler)
    content, content_type, resolved = asyncio.run(media._fetch_image("https://tibia.fandom.com/wiki/Special:FilePath/Terra_Mantle.gif"))
    assert content == png_bytes() and content_type == "image/png"
    assert httpx.URL(resolved).host == "static.wikia.nocookie.net"
    assert seen == [("tibia.fandom.com", "/api.php"), ("static.wikia.nocookie.net", "/tibia/redirect.webp"), ("static.wikia.nocookie.net", "/tibia/final.png")]


def test_downloader_rejects_unallowlisted_hosts_and_html(monkeypatch):
    with pytest.raises(media.UnsafeMediaError, match="not allowed"):
        media.validate_remote_url("https://images.example/image.png")

    def handler(request: httpx.Request):
        if request.url.host == "tibia.fandom.com":
            return httpx.Response(200, json={"query": {"pages": {"1": {"imageinfo": [{"url": "https://static.wikia.nocookie.net/tibia/not-image"}]}}}})
        return httpx.Response(200, content=b"<html>blocked</html>", headers={"Content-Type": "text/html"})
    install_transport(monkeypatch, handler)
    with pytest.raises(media.UnsafeMediaError, match="content type"):
        asyncio.run(media._fetch_image("https://tibia.fandom.com/wiki/Special:FilePath/Test.gif"))


def test_forbidden_classification_and_existing_cache_preservation(db, tmp_path, monkeypatch):
    response = httpx.Response(403, request=httpx.Request("GET", "https://tibia.fandom.com/wiki/Special:FilePath/Test.gif?token=hidden"))
    forbidden = httpx.HTTPStatusError("forbidden", request=response.request, response=response)
    assert classify_exception(forbidden) == (
        "provider_forbidden", 403, False, "Provider rejected the resource request with HTTP 403.",
    )
    old_file = tmp_path / "working.png"
    old_file.write_bytes(png_bytes())
    asset = MediaAsset(
        asset_key="item:test", source_url="https://tibia.fandom.com/wiki/Special:FilePath/Test.gif",
        local_path=str(old_file), content_type="image/png", size_bytes=len(png_bytes()),
        sha256_hash="a" * 64, status="cached", last_fetched_at=datetime.now(UTC),
    )
    db.add(asset); db.commit()

    async def fail(_url):
        raise forbidden
    monkeypatch.setattr(media, "_fetch_image", fail)
    outcome = asyncio.run(media.cache_media_asset(
        db, asset_key="item:test", source_url=asset.source_url, force_refetch=True,
    ))
    db.refresh(asset)
    assert outcome.result == "failed" and outcome.error_category == "provider_forbidden"
    assert asset.status == "cached" and asset.local_path == str(old_file)
    assert old_file.read_bytes() == png_bytes()


def test_canary_persists_gate_without_job_or_maintenance_and_unlocks_only_images(db, client, monkeypatch):
    admin = make_user(db, username="image_canary_admin", is_superuser=True)
    job = SyncService.create_job(
        db, job_type="full", requester=admin.username, requested_by_user_id=admin.id,
        operation_label="Targeted image retry test", maintenance_requested=False,
    )
    phases = db.query(SyncJobPhase).filter_by(job_id=job.id).all()
    images = next(row for row in phases if row.phase_key == "images")
    creatures = next(row for row in phases if row.phase_key == "creatures")
    images.status = "failed"; images.processed_count = 100; images.failed_count = 96
    creatures.status = "failed"; creatures.failed_count = 1
    job.status = "completed_with_errors"
    db.commit()

    retry_path = f"/api/v1/admin/sync/jobs/{job.id}/phases/images/resume"
    blocked = client.post(retry_path, headers=auth(admin))
    assert blocked.status_code == 409 and "canary" in blocked.json()["detail"]

    async def successful_canary(*_args, **_kwargs):
        return {"total": 30, "succeeded": 30, "errors": 0, "failure_categories": {}, "samples": []}
    monkeypatch.setattr(SyncService, "sync_images", staticmethod(successful_canary))
    canary = client.post("/api/v1/admin/sync/images/canary", headers=auth(admin), json={"limit": 30})
    assert canary.status_code == 200 and canary.json()["passed"] is True
    setting = db.query(SystemSettings).filter_by(key="sync_images_canary").one()
    assert json.loads(setting.value)["failed"] == 0
    assert db.query(MaintenanceHold).count() == 0

    resumed = client.post(retry_path, headers=auth(admin))
    assert resumed.status_code == 200
    db.refresh(images); db.refresh(creatures); db.refresh(job)
    assert images.status == "pending" and images.processed_count == 0 and images.failed_count == 0
    assert creatures.status == "failed"
    assert job.status == "pending"
    assert db.query(SyncJobError).filter_by(job_id=job.id, phase_key="creatures").count() == 0
