from __future__ import annotations

import io
import socket
from types import SimpleNamespace

import pytest
from fastapi import Response, status
from PIL import Image

from app.core.security import create_access_token
from app.models.guild import Announcement
from app.services import media_asset_service as media
from app.api.v1.endpoints.health import health_check, readiness_check
from tests.conftest import make_user


def _auth_headers(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(username)}"}


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color=(20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def test_legacy_admin_router_requires_global_admin(client, db):
    user = make_user(db, username="member", is_superuser=False)
    admin = make_user(db, username="globaladmin", is_superuser=True)
    db.commit()

    assert client.get("/api/v1/admin/creatures").status_code == 401
    assert client.get("/api/v1/admin/creatures", headers=_auth_headers(user.username)).status_code == 403
    response = client.get("/api/v1/admin/creatures", headers=_auth_headers(admin.username))
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_category_upload_rejects_non_admin_and_svg(client, db):
    leader = make_user(db, username="leader", guild_rank="Leader", is_superuser=False)
    admin = make_user(db, username="uploadadmin", is_superuser=True)
    db.commit()

    denied = client.post(
        "/api/v1/guild-management/settings/category-images/upload?category=demons",
        headers=_auth_headers(leader.username),
        files={"file": ("image.png", _png_bytes(), "image/png")},
    )
    assert denied.status_code == 403

    rejected = client.post(
        "/api/v1/guild-management/settings/category-images/upload?category=demons",
        headers=_auth_headers(admin.username),
        files={"file": ("image.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")},
    )
    assert rejected.status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "10.1.2.3", "::1"])
def test_remote_media_rejects_non_public_addresses(host):
    with pytest.raises(media.UnsafeMediaError):
        media.validate_remote_url(f"http://[{host}]/image.png" if ":" in host else f"http://{host}/image.png")


def test_remote_media_rejects_dns_resolving_private(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))],
    )
    with pytest.raises(media.UnsafeMediaError):
        media.validate_remote_url("https://images.example/image.png")


def test_remote_media_rejects_private_connected_peer():
    stream = SimpleNamespace(get_extra_info=lambda _name: ("127.0.0.1", 443))
    response = SimpleNamespace(extensions={"network_stream": stream})
    with pytest.raises(media.UnsafeMediaError):
        media._validate_connected_peer(response)


def test_raster_validation_uses_actual_bytes():
    content_type, extension = media.validate_raster_image(_png_bytes(), "image/png")
    assert (content_type, extension) == ("image/png", ".png")
    with pytest.raises(media.UnsafeMediaError):
        media.validate_raster_image(b"not an image", "image/png")
    with pytest.raises(media.UnsafeMediaError):
        media.validate_raster_image(_png_bytes(), "image/jpeg")


def test_svg_placeholder_text_is_xml_escaped():
    escaped = media.escape_svg_text("<tag> & 'single' \"double\"", limit=100)
    assert escaped == '&lt;tag&gt; &amp; &apos;single&apos; &quot;double&quot;'
    assert "<tag>" not in escaped


def test_guild_reads_are_scoped_and_cross_guild_is_forbidden(client, db):
    member = make_user(db, username="guildmember", guild_name="Guild One")
    admin = make_user(db, username="scopeadmin", guild_name="Admins", is_superuser=True)
    db.add_all([
        Announcement(title="One", content="One", author_id=member.id, guild_name="Guild One"),
        Announcement(title="Two", content="Two", author_id=admin.id, guild_name="Guild Two"),
    ])
    db.commit()

    own = client.get("/api/v1/guild/announcements", headers=_auth_headers(member.username))
    assert own.status_code == 200
    assert [row["title"] for row in own.json()] == ["One"]

    forbidden = client.get(
        "/api/v1/guild/announcements?guild_name=Guild%20Two",
        headers=_auth_headers(member.username),
    )
    assert forbidden.status_code == 403

    admin_view = client.get(
        "/api/v1/guild/announcements?guild_name=Guild%20Two",
        headers=_auth_headers(admin.username),
    )
    assert admin_view.status_code == 200
    assert [row["title"] for row in admin_view.json()] == ["Two"]


class _UnavailableDatabase:
    def execute(self, _statement):
        raise OSError("storage unavailable")


def test_health_endpoints_report_database_failure_as_unavailable():
    ready_response = Response()
    assert readiness_check(ready_response, _UnavailableDatabase()) == {"status": "not_ready", "db": "unavailable"}
    assert ready_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    health_response = Response()
    payload = health_check(health_response, _UnavailableDatabase())
    assert health_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert payload["status"] == "degraded"
    assert payload["db"] == "unavailable"
    assert payload["external_sync"]["active_jobs"] is None
