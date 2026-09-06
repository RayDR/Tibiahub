from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

import app.api.v1.items as items_api
import app.services.media_asset_service as media_service
from app.knowledge.models import KnowledgeEntity
from app.models.creature import Creature
from app.models.external_data import Item
from app.models.loot import Loot
from app.models.media_asset import MediaAsset
from app.services.item_media_binding_service import ItemMediaBindingService


def _item(db, name: str, *, item_id: int | None = None, slug_suffix: str = "") -> Item:
    slug = name.casefold().replace(" ", "-") + slug_suffix
    entity = KnowledgeEntity(
        entity_type="item",
        canonical_name=name,
        slug=slug,
        language_neutral_id=f"item:test:{uuid4()}",
    )
    db.add(entity)
    db.flush()
    row = Item(
        id=item_id,
        name=name,
        normalized_name=name.casefold(),
        slug=entity.slug,
        external_id=str(uuid4()),
        source_name="tibiawiki",
        image_url="https://tibia.fandom.com/wiki/Special:FilePath/External.gif",
        knowledge_entity_id=entity.uuid,
    )
    db.add(row)
    db.flush()
    return row


def _loot(db, name: str, *, loot_id: int | None = None) -> Loot:
    creature = Creature(
        name=f"Carrier {uuid4()}",
        normalized_name=f"carrier {uuid4()}",
        slug=f"carrier-{uuid4()}",
        is_hidden=False,
    )
    db.add(creature)
    db.flush()
    row = Loot(id=loot_id, creature_id=creature.id, item_name=name, normalized_name=name.casefold())
    db.add(row)
    db.flush()
    return row


def _asset(db, tmp_path: Path, key: str, payload: bytes, *, status: str = "cached", exists: bool = True) -> MediaAsset:
    path = tmp_path / f"{uuid4()}.gif"
    if exists:
        path.write_bytes(payload)
    asset = MediaAsset(
        asset_key=key,
        status=status,
        local_path=str(path),
        content_type="image/gif",
        size_bytes=len(payload),
    )
    db.add(asset)
    db.flush()
    return asset


def _patch_session(monkeypatch, db) -> None:
    monkeypatch.setattr(
        items_api,
        "SessionLocal",
        sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False),
    )


def test_canonical_binding_survives_rename_and_cannot_cross_numeric_loot_id(
    client, db, monkeypatch, tmp_path,
):
    _patch_session(monkeypatch, db)
    canonical = _item(db, "Canonical Item", item_id=1)
    legacy = _loot(db, "Different Loot Item", loot_id=1)
    canonical_asset = _asset(db, tmp_path, "item:bound-canonical", b"canonical")
    legacy_asset = _asset(db, tmp_path, "item:different_loot_item", b"legacy")
    canonical.image_asset_id = canonical_asset.id
    legacy.image_asset_id = legacy_asset.id
    canonical_id = canonical.knowledge_entity_id
    before_rename = items_api._canonical_item_descriptor(db, canonical)
    assert before_rename.status == "cached" and before_rename.asset_key == canonical_asset.asset_key
    legacy_descriptor = items_api._legacy_loot_descriptor(db, legacy)
    assert legacy_descriptor.status == "cached" and legacy_descriptor.asset_key == legacy_asset.asset_key
    canonical.name = "Renamed Canonical Item"
    canonical.slug = "renamed-canonical-item"
    db.commit()
    canonical_url = f"/api/v1/items/{canonical_id}/image?placeholder=false"
    assert client.get("/api/v1/items/1/image?placeholder=false").status_code == 422
    assert client.get(canonical_url).content == b"canonical"


def test_explicit_binding_wins_and_unbound_exact_bridge_is_temporary(
    db, tmp_path,
):
    bound = _item(db, "Bridge Name")
    linked = _asset(db, tmp_path, "item:explicit-link", b"linked")
    _asset(db, tmp_path, media_service.build_legacy_item_asset_key(bound.name), b"bridge")
    bound.image_asset_id = linked.id

    unbound = _item(db, "Exact Legacy")
    _asset(db, tmp_path, media_service.build_legacy_item_asset_key(unbound.name), b"exact")
    fuzzy = _item(db, "Near Match")
    _asset(db, tmp_path, "item:near_match_extra", b"wrong")
    bound_descriptor = items_api._canonical_item_descriptor(db, bound)
    unbound_descriptor = items_api._canonical_item_descriptor(db, unbound)
    fuzzy_descriptor = items_api._canonical_item_descriptor(db, fuzzy)
    assert bound_descriptor.status == "cached" and bound_descriptor.asset_key == linked.asset_key
    assert unbound_descriptor.status == "cached" and unbound_descriptor.asset_key == "item:exact_legacy"
    assert fuzzy_descriptor.status == "missing"


def test_public_media_descriptor_requires_verified_local_file(client, db, tmp_path):
    available = _item(db, "Available Item")
    available_asset = _asset(db, tmp_path, "item:available", b"available")
    available.image_asset_id = available_asset.id

    missing_file = _item(db, "Missing File Item")
    missing_file.image_asset_id = _asset(db, tmp_path, "item:missing-file", b"gone", exists=False).id
    for status in ("failed", "missing", "pending"):
        row = _item(db, f"{status.title()} Item")
        row.image_asset_id = _asset(db, tmp_path, f"item:{status}", b"unused", status=status).id
    db.flush()

    payload = client.get(f"/api/v1/items/{available.slug}").json()
    assert payload["media"] == {
        "status": "available",
        "url": f"/api/v1/items/{available.knowledge_entity_id}/image?placeholder=false",
    }
    assert "tibia.fandom.com" not in payload["media"]["url"]

    for row in [missing_file, *db.query(Item).filter(Item.name.in_(["Failed Item", "Missing Item", "Pending Item"])).all()]:
        media = client.get(f"/api/v1/items/{row.slug}").json()["media"]
        assert media == {"status": "unavailable", "url": None}


def test_category_visual_excludes_cached_asset_without_file(client, db, tmp_path):
    item = _item(db, "Broken Category Visual")
    item.image_asset_id = _asset(db, tmp_path, "item:broken-visual", b"gone", exists=False).id
    db.flush()

    assert client.get("/api/v1/catalog/category-visuals").json()["items"] is None


def test_reconciliation_preview_apply_idempotency_and_exactness(db, tmp_path, monkeypatch):
    eligible = _item(db, "Eligible Relic")
    eligible_asset = _asset(
        db,
        tmp_path,
        media_service.build_legacy_item_asset_key(eligible.name),
        b"eligible",
    )
    _item(db, "Near Relic")
    _asset(db, tmp_path, "item:near_relic_extra", b"near")
    _item(db, "Ambiguous Relic")
    _item(db, "Ambiguous Relic", slug_suffix="-two")
    _asset(db, tmp_path, "item:ambiguous_relic", b"ambiguous")
    unresolved = Item(name="Unresolved", normalized_name="unresolved", slug="unresolved")
    db.add(unresolved)
    db.flush()

    async def unexpected_download(*_args, **_kwargs):
        raise AssertionError("reconciliation must not download media")

    monkeypatch.setattr(media_service, "cache_media_asset", unexpected_download)
    preview = ItemMediaBindingService.reconcile(db, apply=False)
    assert preview["mode"] == "preview" and preview["network_performed"] is False
    assert preview["eligible"] == 1 and preview["bound"] == 0
    assert preview["ambiguous"] == 2 and preview["unresolved_canonical_binding"] == 1
    assert eligible.image_asset_id is None

    applied = ItemMediaBindingService.reconcile(db, apply=True)
    assert applied["eligible"] == 1 and applied["bound"] == 1
    assert eligible.image_asset_id == eligible_asset.id
    db.flush()
    repeated = ItemMediaBindingService.reconcile(db, apply=True)
    assert repeated["already_bound"] == 1 and repeated["bound"] == 0
