"""Exact, local-only reconciliation of canonical Items to legacy media."""
from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.external_data import Item
from app.models.media_asset import MediaAsset
from app.services.media_asset_service import build_legacy_item_asset_key


REPORT_KEYS = (
    "scanned",
    "already_bound",
    "eligible",
    "bound",
    "no_legacy_asset",
    "asset_not_cached",
    "local_file_missing",
    "ambiguous",
    "unresolved_canonical_binding",
)


class ItemMediaBindingService:
    """Bind only one exact canonical-name key to one verified local asset."""

    @staticmethod
    def reconcile(db: Session, *, apply: bool = False) -> dict[str, Any]:
        query = db.query(Item).order_by(Item.id.asc())
        if apply:
            query = query.with_for_update()
        items = query.all()
        legacy_keys = {
            row.id: build_legacy_item_asset_key(row.name)
            for row in items
            if row.knowledge_entity_id is not None
        }
        key_counts = Counter(key for key in legacy_keys.values() if key)
        requested_keys = set(key_counts)
        assets = (
            db.query(MediaAsset)
            .filter(MediaAsset.asset_key.in_(requested_keys))
            .all()
            if requested_keys
            else []
        )
        assets_by_key: dict[str, list[MediaAsset]] = {}
        for asset in assets:
            assets_by_key.setdefault(asset.asset_key, []).append(asset)

        counts = Counter({key: 0 for key in REPORT_KEYS})
        for item in items:
            counts["scanned"] += 1
            if item.knowledge_entity_id is None:
                counts["unresolved_canonical_binding"] += 1
                continue
            if item.image_asset_id is not None:
                counts["already_bound"] += 1
                continue

            legacy_key = legacy_keys.get(item.id)
            if not legacy_key:
                counts["no_legacy_asset"] += 1
                continue
            matches = assets_by_key.get(legacy_key, [])
            if key_counts[legacy_key] != 1 or len(matches) > 1:
                counts["ambiguous"] += 1
                continue
            if not matches:
                counts["no_legacy_asset"] += 1
                continue
            asset = matches[0]
            if asset.status != "cached":
                counts["asset_not_cached"] += 1
                continue
            if not asset.file_exists():
                counts["local_file_missing"] += 1
                continue

            counts["eligible"] += 1
            if apply:
                item.image_asset_id = asset.id
                counts["bound"] += 1

        return {
            key: counts[key]
            for key in REPORT_KEYS
        } | {
            "mode": "apply" if apply else "preview",
            "network_performed": False,
        }
