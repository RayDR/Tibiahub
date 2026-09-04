from __future__ import annotations

import asyncio
import io
from pathlib import Path

import httpx
from PIL import Image

from app.api.v1.local_media import LocalMediaDescriptor, _bridge_legacy_item_descriptor
from app.core.security import create_access_token
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType
from app.models import Creature, HuntZone
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc
from app.models.media_asset import MediaAsset
from app.services import media_asset_service as media
from app.services import media_path_service as media_paths
from app.services.media_reconciliation_service import MediaReconciliationService
from tests.conftest import make_user


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color=(20, 40, 80)).save(output, format="PNG")
    return output.getvalue()


def _entity(db, entity_type: str, name: str) -> KnowledgeEntity:
    if db.get(KnowledgeEntityType, entity_type) is None:
        db.add(KnowledgeEntityType(entity_type=entity_type, display_name=entity_type.title()))
        db.flush()
    row = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.casefold().replace(" ", "-"),
        language_neutral_id=f"media-test:{entity_type}:{name}",
    )
    db.add(row)
    db.flush()
    return row


def test_media_root_and_legacy_reads_are_independent_of_process_cwd(tmp_path, monkeypatch):
    configured = tmp_path / "configured-media"
    backend_root = tmp_path / "checkout" / "backend"
    legacy_file = backend_root / "backend" / "storage" / "media" / "legacy.gif"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_bytes(b"legacy")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.setattr(media_paths.settings, "MEDIA_STORAGE_ROOT", str(configured))
    monkeypatch.setattr(media_paths, "BACKEND_ROOT", backend_root)
    monkeypatch.chdir(elsewhere)

    assert media_paths.media_storage_root() == configured.resolve()
    assert media_paths.resolve_media_local_path("backend/storage/media/legacy.gif") == legacy_file.resolve()
    assert media_paths.resolve_media_local_path("backend/storage/media/../../../../etc/passwd") is None
    assert media_paths.resolve_media_local_path("../legacy.gif") is None


def test_new_media_write_uses_configured_absolute_root(tmp_path, monkeypatch, db):
    configured = tmp_path / "configured-media"
    elsewhere = tmp_path / "worker-cwd"
    elsewhere.mkdir()
    monkeypatch.setattr(media_paths.settings, "MEDIA_STORAGE_ROOT", str(configured))
    monkeypatch.chdir(elsewhere)

    async def fetched(_source_url):
        return _png_bytes(), "image/png", "https://static.wikia.nocookie.net/tibia/example.png"

    monkeypatch.setattr(media, "_fetch_image", fetched)
    outcome = asyncio.run(media.cache_media_asset(
        db,
        asset_key="creature:cwd_independent",
        source_url="https://tibia.fandom.com/wiki/Special:FilePath/Example.png",
    ))

    assert outcome.result == "created"
    assert outcome.asset is not None
    stored = Path(outcome.asset.local_path)
    assert stored.is_absolute()
    assert stored.parent == configured.resolve()
    assert stored.read_bytes() == _png_bytes()


def test_canonical_item_bridge_is_exact_and_not_fuzzy(db, tmp_path):
    exact_file = tmp_path / "exact.gif"
    exact_file.write_bytes(b"exact")
    db.add_all([
        MediaAsset(asset_key="item:behemoth_claws", local_path=str(exact_file), status="cached"),
        MediaAsset(asset_key="item:behemoth_claw_typo", local_path=str(exact_file), status="cached"),
    ])
    db.flush()
    descriptor = LocalMediaDescriptor(
        local_path=None,
        content_type=None,
        size_bytes=None,
        asset_hash=None,
        asset_key="item:knowledge:00000000-0000-0000-0000-000000000001",
        status="missing",
        fallback_label="Behemoth Claw",
    )

    assert media.build_canonical_item_asset_key("abc") == "item:knowledge:abc"
    assert media.build_legacy_item_asset_key("Behemoth Claw.gif") == "item:behemoth_claw"
    assert _bridge_legacy_item_descriptor(db, descriptor) is descriptor


def test_category_visual_can_reuse_exact_legacy_item_asset(client, db, tmp_path):
    entity = _entity(db, "item", "Legacy Visual Relic")
    item = Item(name="Legacy Visual Relic", normalized_name="legacy visual relic", slug="legacy-visual-relic", knowledge_entity_id=entity.uuid)
    media_file = tmp_path / "legacy-visual.gif"
    media_file.write_bytes(b"GIF89a")
    db.add(item)
    db.add(MediaAsset(
        asset_key=media.build_legacy_item_asset_key(item.name),
        status="cached",
        local_path=str(media_file),
        content_type="image/gif",
    ))
    db.flush()

    response = client.get("/api/v1/catalog/category-visuals")

    assert response.status_code == 200
    assert response.json()["items"] == f"/api/v1/items/{item.id}/image?placeholder=false"


def test_media_failure_taxonomy_is_specific_and_sanitized(db, monkeypatch):
    unsafe = media.UnsafeMediaError("raw provider payload", error_code="unsupported_content_type")

    async def failed(_source_url):
        raise unsafe

    monkeypatch.setattr(media, "_fetch_image", failed)
    outcome = asyncio.run(media.cache_media_asset(
        db,
        asset_key="creature:bad_payload",
        source_url="https://tibia.fandom.com/wiki/Special:FilePath/Bad.gif?secret=value",
    ))

    assert outcome.result == "skipped"
    assert outcome.error_category == "unsupported_content_type"
    assert outcome.safe_message == "The provider response has an unsupported content type."
    assert outcome.safe_url == "https://tibia.fandom.com/wiki/Special:FilePath/Bad.gif"
    assert "raw provider payload" not in outcome.asset.error_message
    assert "secret" not in outcome.asset.error_message

    request = httpx.Request("GET", "https://tibia.fandom.com/image.gif")
    rate_response = httpx.Response(429, request=request)
    category, status, retryable, _message = media._classify_media_exception(
        httpx.HTTPStatusError("raw", request=request, response=rate_response)
    )
    assert (category, status, retryable) == ("provider_rate_limited", 429, True)
    timeout = media._classify_media_exception(httpx.ReadTimeout("raw", request=request))
    assert timeout[:3] == ("provider_timeout", None, True)


def test_reconciliation_is_bounded_sanitized_and_network_free(db, tmp_path, monkeypatch):
    creature = Creature(name="Failed Beast", normalized_name="failed beast", slug="failed-beast", is_hidden=False)
    db.add(creature)
    item_entity = _entity(db, "item", "Bridge Relic")
    npc_entity = _entity(db, "npc", "No Image Guide")
    zone_entity = _entity(db, "hunt_zone", "Missing File Grounds")
    location_entity = _entity(db, "location", "No Image Place")
    item = Item(name="Bridge Relic", normalized_name="bridge relic", slug="bridge-relic", knowledge_entity_id=item_entity.uuid)
    npc = TibiaWikiNpc(name="No Image Guide", normalized_name="no image guide", slug="no-image-guide", external_id="npc:1", source_name="tibiawiki", knowledge_entity_id=npc_entity.uuid)
    zone = HuntZone(name="Missing File Grounds", normalized_name="missing file grounds", slug="missing-file-grounds", source_provider="tibiawiki", external_id="zone:1", knowledge_entity_id=zone_entity.uuid)
    location = TibiaWikiLocation(name="No Image Place", normalized_name="no image place", slug="no-image-place", external_id="location:1", source_name="tibiawiki", knowledge_entity_id=location_entity.uuid)
    bridge_file = tmp_path / "bridge.gif"
    bridge_file.write_bytes(b"bridge")
    db.add_all([item, npc, zone, location])
    db.flush()
    db.add_all([
        MediaAsset(
            asset_key=media.build_creature_asset_key(creature), status="failed",
            error_message="provider_timeout: The provider request timed out.",
            source_url="https://example.invalid/private?token=secret",
            local_path="/private/not-exposed.gif",
        ),
        MediaAsset(asset_key=media.build_legacy_item_asset_key(item.name), status="cached", local_path=str(bridge_file)),
        MediaAsset(asset_key=media.build_zone_asset_key(zone), status="cached", local_path=str(tmp_path / "absent.gif")),
    ])
    db.flush()
    before = db.new.copy(), db.dirty.copy(), db.deleted.copy()

    async def unexpected_network(_source_url):
        raise AssertionError("reconciliation must not fetch media")

    monkeypatch.setattr(media, "_fetch_image", unexpected_network)
    report = MediaReconciliationService.report(db, sample_limit=1)

    groups = {group["entity_type"]: group for group in report["groups"]}
    assert groups["creature"]["counts"]["failed"] == 1
    assert groups["creature"]["failure_codes"] == {"provider_timeout": 1}
    assert groups["item"]["counts"]["legacy_key_bridge"] == 1
    assert groups["npc"]["counts"]["no_media_asset"] == 1
    assert groups["hunt_zone"]["counts"]["local_file_missing"] == 1
    assert groups["location"]["counts"]["no_media_asset"] == 1
    assert all(len(group["samples"]) <= 1 for group in report["groups"])
    assert report["download_performed"] is False and report["read_only"] is True
    assert report["location_media_contract"]["ingestion_enabled"] is False
    assert report["category_images"]["uses_media_asset"] is False
    serialized = str(report)
    assert "/private/" not in serialized and "token=secret" not in serialized
    assert before == (db.new.copy(), db.dirty.copy(), db.deleted.copy())


def test_reconciliation_endpoint_is_admin_only_and_bounded(client, db):
    admin = make_user(db, username="media_reconciliation_admin", is_superuser=True)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}

    assert client.get("/api/v1/admin/sync/media/reconciliation").status_code == 401
    response = client.get(
        "/api/v1/admin/sync/media/reconciliation",
        params={"sample_limit": 0},
        headers=headers,
    )
    assert response.status_code == 200
    assert all(group["samples"] == [] for group in response.json()["groups"])
    assert client.get(
        "/api/v1/admin/sync/media/reconciliation",
        params={"sample_limit": 51},
        headers=headers,
    ).status_code == 422
