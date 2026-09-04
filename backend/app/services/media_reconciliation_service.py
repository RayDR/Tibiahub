"""Read-only, network-free reconciliation of canonical media coverage."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models import Creature, HuntZone
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc
from app.models.media_asset import MediaAsset
from app.services import media_asset_service


MEDIA_RECONCILIATION_STATUSES = (
    "cached",
    "missing",
    "failed",
    "pending",
    "no_media_asset",
    "legacy_key_bridge",
    "local_file_missing",
    "unresolved_canonical_binding",
)


class MediaReconciliationService:
    """Build aggregate diagnostics without fetching or mutating media."""

    @staticmethod
    def _asset_status(asset: MediaAsset | None) -> tuple[str, str | None]:
        if asset is None:
            return "no_media_asset", None
        if asset.status == "cached":
            return ("cached", None) if asset.file_exists() else ("local_file_missing", None)
        status = asset.status if asset.status in {"missing", "failed", "pending"} else "failed"
        error_code = media_asset_service.stored_media_error(asset)[0] if status in {"missing", "failed"} else None
        return status, error_code

    @staticmethod
    def _group(
        entity_type: str,
        rows: Iterable[tuple[str, str, str, str | None]],
        *,
        sample_limit: int,
    ) -> dict[str, Any]:
        counts = Counter({status: 0 for status in MEDIA_RECONCILIATION_STATUSES})
        failure_codes: Counter[str] = Counter()
        samples: list[dict[str, str]] = []
        total = 0
        for entity_id, name, status, error_code in rows:
            total += 1
            counts[status] += 1
            if error_code:
                failure_codes[error_code] += 1
            if len(samples) < sample_limit and status != "cached":
                sample = {"entity_id": entity_id, "name": name, "status": status}
                if error_code:
                    sample["error_code"] = error_code
                samples.append(sample)
        return {
            "entity_type": entity_type,
            "total": total,
            "counts": {status: counts[status] for status in MEDIA_RECONCILIATION_STATUSES},
            "failure_codes": dict(sorted(failure_codes.items())),
            "samples": samples,
        }

    @staticmethod
    def report(db: Session, *, sample_limit: int = 10) -> dict[str, Any]:
        assets = db.query(MediaAsset).all()
        by_key = {asset.asset_key: asset for asset in assets}
        status_by_asset_id: dict[int, tuple[str, str | None]] = {}

        def asset_status(asset: MediaAsset | None) -> tuple[str, str | None]:
            if asset is None:
                return "no_media_asset", None
            if asset.id not in status_by_asset_id:
                status_by_asset_id[asset.id] = MediaReconciliationService._asset_status(asset)
            return status_by_asset_id[asset.id]

        def creatures():
            for row in db.query(Creature).order_by(Creature.id).all():
                status, error = asset_status(
                    by_key.get(media_asset_service.build_creature_asset_key(row))
                )
                yield str(row.id), row.name, status, error

        def npcs():
            for row in db.query(TibiaWikiNpc).order_by(TibiaWikiNpc.id).all():
                status, error = asset_status(
                    by_key.get(media_asset_service.build_npc_asset_key(row))
                )
                yield str(row.knowledge_entity_id), row.name, status, error

        def items():
            for row in db.query(Item).order_by(Item.id).all():
                if row.knowledge_entity_id is None:
                    yield str(row.id), row.name, "unresolved_canonical_binding", None
                    continue
                canonical_key = media_asset_service.build_canonical_item_asset_key(row.knowledge_entity_id)
                canonical_asset = by_key.get(canonical_key)
                canonical_status, canonical_error = asset_status(canonical_asset)
                if canonical_status == "cached":
                    yield str(row.knowledge_entity_id), row.name, canonical_status, canonical_error
                    continue
                legacy_key = media_asset_service.build_legacy_item_asset_key(row.name)
                legacy_asset = by_key.get(legacy_key) if legacy_key else None
                legacy_status, legacy_error = asset_status(legacy_asset)
                if legacy_status == "cached":
                    yield str(row.knowledge_entity_id), row.name, "legacy_key_bridge", None
                elif canonical_asset is not None:
                    yield str(row.knowledge_entity_id), row.name, canonical_status, canonical_error
                elif legacy_asset is not None:
                    yield str(row.knowledge_entity_id), row.name, legacy_status, legacy_error
                else:
                    yield str(row.knowledge_entity_id), row.name, "no_media_asset", None

        def hunt_zones():
            for row in db.query(HuntZone).order_by(HuntZone.id).all():
                if row.knowledge_entity_id is None:
                    yield str(row.id), row.name, "unresolved_canonical_binding", None
                    continue
                status, error = asset_status(
                    by_key.get(media_asset_service.build_zone_asset_key(row))
                )
                yield str(row.knowledge_entity_id), row.name, status, error

        def locations():
            for row in db.query(TibiaWikiLocation).order_by(TibiaWikiLocation.id).all():
                if row.knowledge_entity_id is None:
                    yield str(row.id), row.name, "unresolved_canonical_binding", None
                else:
                    yield str(row.knowledge_entity_id), row.name, "no_media_asset", None

        groups = [
            MediaReconciliationService._group("creature", creatures(), sample_limit=sample_limit),
            MediaReconciliationService._group("npc", npcs(), sample_limit=sample_limit),
            MediaReconciliationService._group("item", items(), sample_limit=sample_limit),
            MediaReconciliationService._group("hunt_zone", hunt_zones(), sample_limit=sample_limit),
            MediaReconciliationService._group("location", locations(), sample_limit=sample_limit),
        ]
        return {
            "generated_at": datetime.now(UTC),
            "read_only": True,
            "download_performed": False,
            "storage": {
                "write_root": "configured_absolute",
                "cwd_independent": True,
                "legacy_cache_read_compatible": True,
            },
            "groups": groups,
            "location_media_contract": {
                "canonical_identity": "knowledge_entity_uuid",
                "local_endpoint": "/api/v1/locations/{identifier}/image",
                "source_requirement": "allowlisted_provider_image_evidence",
                "ingestion_enabled": False,
                "current_coverage": "none",
            },
            "category_images": {
                "storage": "separate_local_category_image_directory",
                "uses_media_asset": False,
                "remote_config_rendered": False,
            },
        }
