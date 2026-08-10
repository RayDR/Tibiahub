from __future__ import annotations

import asyncio

from app.models import Creature
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
