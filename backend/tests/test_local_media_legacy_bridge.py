from pathlib import Path

from app.api.v1.local_media import (
    LocalMediaDescriptor,
    _bridge_legacy_item_descriptor,
)
from app.models.media_asset import MediaAsset


def _descriptor(*, asset_key: str, status: str = "missing") -> LocalMediaDescriptor:
    return LocalMediaDescriptor(
        local_path=None,
        content_type=None,
        size_bytes=None,
        asset_hash=None,
        asset_key=asset_key,
        status=status,
        fallback_label="Behemoth Claw",
    )


def test_canonical_item_reuses_cached_legacy_asset(db, tmp_path: Path):
    media_path = tmp_path / "item_behemoth_claw.webp"
    media_path.write_bytes(b"cached-image")
    asset = MediaAsset(
        asset_key="item:behemoth_claw",
        source_url="https://tibia.fandom.com/wiki/Special:FilePath/Behemoth_Claw.gif",
        local_path=str(media_path),
        content_type="image/webp",
        size_bytes=12,
        sha256_hash="abc123",
        status="cached",
    )
    db.add(asset)
    db.flush()

    resolved = _bridge_legacy_item_descriptor(
        db,
        _descriptor(asset_key="item:knowledge:83b821a1-6fce-4071-8318-cff3de0f3b44"),
    )

    assert resolved.status == "cached"
    assert resolved.asset_key == "item:behemoth_claw"
    assert resolved.local_path == str(media_path)
    assert resolved.content_type == "image/webp"
    assert resolved.size_bytes == 12
    assert resolved.asset_hash == "abc123"


def test_bridge_keeps_canonical_cached_descriptor(db):
    descriptor = LocalMediaDescriptor(
        local_path="canonical.webp",
        content_type="image/webp",
        size_bytes=42,
        asset_hash="canonical",
        asset_key="item:knowledge:canonical",
        status="cached",
        fallback_label="Behemoth Claw",
    )

    assert _bridge_legacy_item_descriptor(db, descriptor) is descriptor


def test_bridge_does_not_cross_entity_types(db):
    descriptor = _descriptor(asset_key="creature:knowledge:behemoth")

    assert _bridge_legacy_item_descriptor(db, descriptor) is descriptor
