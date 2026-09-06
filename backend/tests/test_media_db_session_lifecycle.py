from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Response
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import sessionmaker

import app.api.v1.creatures as creatures_api
import app.api.v1.hunt_zones as hunt_zones_api
import app.api.v1.items as items_api
import app.api.v1.local_media as local_media_api
from app.db import database as database_module
from app.models.creature import Creature
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.media_asset import MediaAsset
from app.services import media_asset_service as media_svc


def _write_asset(tmp_path: Path, file_name: str, content: bytes) -> tuple[Path, str]:
    path = tmp_path / file_name
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def _create_creature(db, *, name: str, slug: str) -> Creature:
    creature = Creature(
        name=name,
        normalized_name=name.casefold(),
        slug=slug,
        hitpoints=120,
        experience=80,
        is_boss=False,
        is_hidden=False,
    )
    db.add(creature)
    db.flush()
    return creature


def _patch_media_session_factories(monkeypatch, db) -> None:
    factory = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    monkeypatch.setattr(items_api, "SessionLocal", factory)
    monkeypatch.setattr(creatures_api, "SessionLocal", factory)
    monkeypatch.setattr(hunt_zones_api, "SessionLocal", factory)


def test_item_cached_media_returns_file_response(client, db, monkeypatch, tmp_path):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="Item Carrier", slug="item-carrier")
    loot = Loot(creature_id=creature.id, item_name="Crystal Coin")
    db.add(loot)
    db.flush()

    content = b"GIF89a-item"
    asset_path, sha256_hash = _write_asset(tmp_path, "item.gif", content)
    db.add(
        MediaAsset(
            asset_key=media_svc.build_loot_asset_key(loot),
            local_path=str(asset_path),
            content_type="image/gif",
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            status="cached",
        )
    )
    db.commit()

    response = client.get(f"/api/v1/items/legacy-loot/{loot.id}/image")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["x-image-source"] == "local-media-asset"
    assert response.headers["x-image-status"] == "cached"
    assert response.headers["etag"] == sha256_hash[:20]


def test_creature_cached_media_returns_file_response(client, db, monkeypatch, tmp_path):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="Cached Creature", slug="cached-creature")

    content = b"GIF89a-creature"
    asset_path, sha256_hash = _write_asset(tmp_path, "creature.gif", content)
    db.add(
        MediaAsset(
            asset_key=media_svc.build_creature_asset_key(creature),
            local_path=str(asset_path),
            content_type="image/gif",
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            status="cached",
        )
    )
    db.commit()

    response = client.get(f"/api/v1/creatures/{creature.id}/image")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["x-image-source"] == "local-media-asset"
    assert response.headers["x-image-status"] == "cached"
    assert response.headers["etag"] == sha256_hash[:20]


def test_hunt_zone_cached_media_returns_file_response(client, db, monkeypatch, tmp_path):
    _patch_media_session_factories(monkeypatch, db)
    zone = HuntZone(
        name="Draken Walls",
        normalized_name="draken walls",
        min_level=100,
        max_level=200,
    )
    db.add(zone)
    db.flush()

    content = b"PNG-zone-data"
    asset_path, sha256_hash = _write_asset(tmp_path, "zone.png", content)
    db.add(
        MediaAsset(
            asset_key=media_svc.build_zone_asset_key(zone),
            local_path=str(asset_path),
            content_type="image/png",
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            status="cached",
        )
    )
    db.commit()

    response = client.get(f"/api/v1/hunt-zones/{zone.id}/map-image")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["x-image-source"] == "local-media-asset"
    assert response.headers["x-image-status"] == "cached"
    assert response.headers["etag"] == sha256_hash[:20]


def test_item_missing_media_placeholder(client, db, monkeypatch):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="Placeholder Carrier", slug="placeholder-carrier")
    loot = Loot(creature_id=creature.id, item_name="Unknown Relic")
    db.add(loot)
    db.commit()

    placeholder_response = client.get(f"/api/v1/items/legacy-loot/{loot.id}/image")
    assert placeholder_response.status_code == 200
    assert placeholder_response.headers["x-image-source"] == "placeholder"
    assert placeholder_response.headers["x-image-status"] == "missing"
    assert placeholder_response.headers["content-type"].startswith("image/svg+xml")


def test_item_placeholder_false_returns_404(client, db, monkeypatch):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="No Placeholder Carrier", slug="no-placeholder-carrier")
    loot = Loot(creature_id=creature.id, item_name="No Placeholder Item")
    db.add(loot)
    db.commit()

    response = client.get(f"/api/v1/items/legacy-loot/{loot.id}/image?placeholder=false")

    assert response.status_code == 404
    assert response.headers["x-image-source"] == "unavailable"
    assert response.headers["x-image-status"] == "missing"


def test_creature_placeholder_false_returns_404(client, db, monkeypatch):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="No Image Creature", slug="no-image-creature")
    db.commit()

    response = client.get(f"/api/v1/creatures/{creature.id}/image?placeholder=false")

    assert response.status_code == 404
    assert response.headers["x-image-source"] == "unavailable"
    assert response.headers["x-image-status"] == "missing"


def test_hunt_zone_missing_media_returns_placeholder(client, db, monkeypatch):
    _patch_media_session_factories(monkeypatch, db)
    zone = HuntZone(
        name="No Map Zone",
        normalized_name="no map zone",
        min_level=30,
        max_level=60,
    )
    db.add(zone)
    db.commit()

    response = client.get(f"/api/v1/hunt-zones/{zone.id}/map-image")

    assert response.status_code == 200
    assert response.headers["x-image-source"] == "placeholder"
    assert response.headers["x-image-status"] == "missing"
    assert response.headers["content-type"].startswith("image/svg+xml")


def test_item_media_etag_304_behavior(client, db, monkeypatch, tmp_path):
    _patch_media_session_factories(monkeypatch, db)
    creature = _create_creature(db, name="ETag Carrier", slug="etag-carrier")
    loot = Loot(creature_id=creature.id, item_name="ETag Item")
    db.add(loot)
    db.flush()

    content = b"GIF89a-etag"
    asset_path, sha256_hash = _write_asset(tmp_path, "etag.gif", content)
    db.add(
        MediaAsset(
            asset_key=media_svc.build_loot_asset_key(loot),
            local_path=str(asset_path),
            content_type="image/gif",
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            status="cached",
        )
    )
    db.commit()

    expected_etag = sha256_hash[:20]
    response = client.get(
        f"/api/v1/items/legacy-loot/{loot.id}/image",
        headers={"If-None-Match": expected_etag},
    )

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == expected_etag


class _TrackingSession:
    def __init__(self, session, state: dict[str, bool]):
        self._session = session
        self._state = state

    def rollback(self):
        return self._session.rollback()

    def close(self):
        self._state["closed"] = True
        return self._session.close()

    def __getattr__(self, name):
        return getattr(self._session, name)


def _tracking_factory(bind, state: dict[str, bool]):
    base_factory = sessionmaker(bind=bind, autocommit=False, autoflush=False)

    def _factory():
        state["closed"] = False
        return _TrackingSession(base_factory(), state)

    return _factory


@pytest.mark.parametrize(
    ("module", "path"),
    [
        (items_api, "/api/v1/items/legacy-loot/{item_id}/image"),
        (creatures_api, "/api/v1/creatures/{creature_id}/image"),
        (hunt_zones_api, "/api/v1/hunt-zones/{zone_id}/map-image"),
    ],
)
def test_media_session_closed_before_fileresponse_delivery(client, db, monkeypatch, tmp_path, module, path):
    state = {"closed": False}
    monkeypatch.setattr(module, "SessionLocal", _tracking_factory(db.get_bind(), state))

    def _spy_file_response(*_args, **kwargs):
        assert state["closed"] is True
        return Response(status_code=200, headers=kwargs.get("headers", {}), media_type=kwargs.get("media_type"))

    monkeypatch.setattr(local_media_api, "FileResponse", _spy_file_response)

    creature = _create_creature(db, name="Session Check Creature", slug="session-check-creature")
    loot = Loot(creature_id=creature.id, item_name="Session Check Item")
    zone = HuntZone(name="Session Check Zone", normalized_name="session check zone", min_level=20, max_level=40)
    db.add_all([loot, zone])
    db.flush()

    file_bytes = b"payload"
    file_path, sha256_hash = _write_asset(tmp_path, f"{module.__name__.split('.')[-1]}.bin", file_bytes)

    if module is items_api:
        asset_key = media_svc.build_loot_asset_key(loot)
        target = path.format(item_id=loot.id)
    elif module is creatures_api:
        asset_key = media_svc.build_creature_asset_key(creature)
        target = path.format(creature_id=creature.id)
    else:
        asset_key = media_svc.build_zone_asset_key(zone)
        target = path.format(zone_id=zone.id)

    db.add(
        MediaAsset(
            asset_key=asset_key,
            local_path=str(file_path),
            content_type="application/octet-stream",
            size_bytes=len(file_bytes),
            sha256_hash=sha256_hash,
            status="cached",
        )
    )
    db.commit()

    response = client.get(target)
    assert response.status_code == 200


def test_database_pool_timeout_option_reaches_create_engine(monkeypatch):
    captured: dict[str, object] = {}

    def fake_create_engine(url, **options):
        captured["url"] = url
        captured["options"] = options
        return object()

    monkeypatch.setattr(database_module, "create_engine", fake_create_engine)

    config = SimpleNamespace(
        DATABASE_POOL_RECYCLE_SECONDS=1800,
        DATABASE_POOL_SIZE=5,
        DATABASE_MAX_OVERFLOW=10,
        DATABASE_POOL_TIMEOUT_SECONDS=5,
        DATABASE_CONNECT_TIMEOUT_SECONDS=10,
        DATABASE_STATEMENT_TIMEOUT_MS=30000,
        DATABASE_IDLE_TRANSACTION_TIMEOUT_MS=60000,
        APP_ENV="production",
        database_url=make_url("postgresql+psycopg2://user:pass@localhost:5432/tibiahub"),
    )

    database_module.create_database_engine(config=config)

    assert captured["options"]["pool_timeout"] == 5


def test_sqlalchemy_pool_timeout_maps_to_database_busy(client, monkeypatch):
    def _raise_timeout(_canonical_id):
        raise SATimeoutError("pool exhausted")

    monkeypatch.setattr(items_api, "_resolve_item_media_descriptor", _raise_timeout)

    response = client.get("/api/v1/items/00000000-0000-0000-0000-000000000001/image")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json()["detail"]["code"] == "database_busy"
