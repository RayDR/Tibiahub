from __future__ import annotations

import asyncio

from app.models import Creature, HuntZone
from app.models.media_asset import MediaAsset
from app.services import media_asset_service
from app.services.sync_service import SyncService


def test_permanent_unsupported_media_becomes_missing(
    db,
    monkeypatch,
):
    calls = 0

    async def unsupported(_source_url):
        nonlocal calls
        calls += 1
        raise media_asset_service.UnsafeMediaError(
            "missing provider image"
        )

    monkeypatch.setattr(
        media_asset_service,
        "_fetch_image",
        unsupported,
    )

    source = (
        "https://tibia.fandom.com/wiki/"
        "Special:FilePath/Missing.gif"
    )

    first = asyncio.run(
        media_asset_service.cache_media_asset(
            db,
            asset_key="creature:missing",
            source_url=source,
        )
    )

    assert first.result == "skipped"
    assert first.asset is not None
    assert first.asset.status == "missing"
    assert calls == 1

    second = asyncio.run(
        media_asset_service.cache_media_asset(
            db,
            asset_key="creature:missing",
            source_url=source,
        )
    )

    assert second.result == "skipped"
    assert calls == 1


def test_image_sync_skips_hidden_and_missing_media(
    db,
    monkeypatch,
):
    visible = Creature(
        name="Visible Creature",
        normalized_name="visible creature",
        slug="visible-creature",
        hitpoints=100,
        experience=100,
        image_url=(
            "https://tibia.fandom.com/wiki/"
            "Special:FilePath/Visible.gif"
        ),
        is_hidden=False,
        is_boss=False,
    )

    hidden = Creature(
        name="Creatures",
        normalized_name="creatures",
        slug="creatures",
        hitpoints=0,
        experience=0,
        image_url=(
            "https://tibia.fandom.com/wiki/"
            "Special:FilePath/Creatures.gif"
        ),
        is_hidden=True,
        is_boss=False,
    )

    db.add_all([visible, hidden])
    db.flush()

    calls = []

    async def skipped(
        _db,
        *,
        asset_key,
        source_url,
        force_refetch=False,
        retry_failed=False,
    ):
        calls.append(asset_key)
        return media_asset_service.MediaFetchOutcome(
            asset=None,
            result="skipped",
            error_category="unsupported_resource",
            safe_message="unsupported",
            retryable=False,
            safe_url=source_url,
        )

    monkeypatch.setattr(
        media_asset_service,
        "cache_media_asset",
        skipped,
    )

    result = asyncio.run(
        SyncService.sync_images(db)
    )

    assert calls == ["creature:visible_creature"]
    assert result["total"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 0
    assert result["status"] == "success"


def test_image_sync_links_cached_hunt_zone_media_through_map_asset_id(db, monkeypatch):
    zone = HuntZone(
        name="Illustrated Grounds",
        normalized_name="illustrated grounds",
        slug="illustrated-grounds",
        source_provider="tibiawiki",
        external_id="2301",
        supplied_fields=["image_reference"],
        map_image_url=(
            "https://tibia.fandom.com/wiki/"
            "Special:FilePath/Illustrated_Grounds.png"
        ),
    )
    db.add(zone)
    db.flush()

    async def cached(
        target_db,
        *,
        asset_key,
        source_url,
        force_refetch=False,
        retry_failed=False,
    ):
        asset = MediaAsset(
            asset_key=asset_key,
            source_url=source_url,
            status="cached",
        )
        target_db.add(asset)
        target_db.flush()
        return media_asset_service.MediaFetchOutcome(asset=asset, result="created")

    monkeypatch.setattr(media_asset_service, "cache_media_asset", cached)

    result = asyncio.run(SyncService.sync_images(db))
    db.refresh(zone)

    assert result["total"] == 1 and result["created"] == 1
    assert zone.map_asset_id is not None
    assert not hasattr(zone, "image_asset_id")
    assert db.get(MediaAsset, zone.map_asset_id).asset_key == "zone:tibiawiki:2301"


def test_image_sync_ignores_legacy_tibiamaps_floor_placeholder(db, monkeypatch):
    db.add(HuntZone(
        name="Legacy Free Text",
        normalized_name="legacy free text",
        slug="legacy-free-text",
        source_provider="tibiamaps",
        map_image_url="https://tibiamaps.github.io/tibia-map-data/floor-07-map.png",
    ))
    db.flush()

    async def unexpected(*args, **kwargs):
        raise AssertionError("legacy floor placeholder must not be cached as zone media")

    monkeypatch.setattr(media_asset_service, "cache_media_asset", unexpected)
    result = asyncio.run(SyncService.sync_images(db))
    assert result["total"] == 0
