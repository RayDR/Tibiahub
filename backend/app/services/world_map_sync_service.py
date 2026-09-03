"""Versioned local ingestion for the authoritative MIT-licensed TibiaMaps data.

Public request paths never call this service and never perform network I/O.
An imported commit is immutable on disk and can be renormalized into newer DB
schemas without fetching TibiaMaps again.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeSearchMetadata
from app.models.world_map import WorldMapDataset, WorldMapFloor, WorldMapMarker
from app.services.text_utils import normalize_search_text


PROVIDER = "tibiamaps/tibia-map-data"
UPSTREAM_URL = "https://github.com/tibiamaps/tibia-map-data"
ATTRIBUTION = "Tibia map data © Mathias Bynens and contributors, used under the MIT License."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("World-map path escapes the configured storage root")
    return candidate


class WorldMapSyncService:
    def __init__(self, db: Session, storage_root: str | Path):
        self.db = db
        self.storage_root = Path(storage_root).resolve()

    @staticmethod
    def _validate_commit(upstream_commit: str) -> str:
        value = (upstream_commit or "").lower()
        if len(value) < 7 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("A hexadecimal upstream commit is required")
        return value

    @staticmethod
    def _read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def import_directory(self, source_root: str | Path, *, upstream_commit: str) -> dict:
        """Validate and atomically retain one immutable upstream commit."""
        upstream_commit = self._validate_commit(upstream_commit)
        source_root = Path(source_root).resolve()
        data_root = source_root / "data"
        bounds_path, markers_path = data_root / "bounds.json", data_root / "markers.json"
        license_path = source_root / "LICENSE-MIT.txt"
        if not bounds_path.is_file() or not markers_path.is_file() or not license_path.is_file():
            raise ValueError("Source must contain data/bounds.json, data/markers.json, and LICENSE-MIT.txt")
        bounds = self._read_json(bounds_path)
        floors = [int(value) for value in bounds.get("floorIDs", [])]
        if floors != list(range(16)):
            raise ValueError("Expected Tibia floors 00 through 15")
        width, height = int(bounds["width"]), int(bounds["height"])

        destination = _inside(self.storage_root, self.storage_root / PROVIDER.replace("/", "-") / upstream_commit)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="world-map-import-", dir=str(destination.parent)))
        try:
            shutil.copy2(license_path, temporary / "LICENSE-MIT.txt")
            imported: list[dict] = []
            for floor in floors:
                map_source = data_root / f"floor-{floor:02d}-map.png"
                path_source = data_root / f"floor-{floor:02d}-path.png"
                if not map_source.is_file() or not path_source.is_file():
                    raise ValueError(f"Missing floor {floor:02d} map or pathfinding PNG")
                for source in (map_source, path_source):
                    with Image.open(source) as image:
                        if image.format != "PNG" or image.size != (width, height):
                            raise ValueError(f"Unexpected floor {floor:02d} image dimensions")
                map_target, path_target = temporary / map_source.name, temporary / path_source.name
                shutil.copy2(map_source, map_target)
                shutil.copy2(path_source, path_target)
                imported.append({
                    "floor": floor, "map_name": map_target.name, "path_name": path_target.name,
                    "map_sha256": _sha256(map_target), "path_sha256": _sha256(path_target),
                })
            shutil.copy2(bounds_path, temporary / "bounds.json")
            shutil.copy2(markers_path, temporary / "markers.json")
            manifest = {
                "provider": PROVIDER, "upstream_url": UPSTREAM_URL, "upstream_commit": upstream_commit,
                "license": "MIT", "attribution": ATTRIBUTION, "bounds": bounds,
                "floors": imported, "markers_sha256": _sha256(temporary / "markers.json"),
            }
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
            )
            if destination.exists():
                stored_manifest = self._read_json(destination / "manifest.json")
                if stored_manifest != manifest:
                    raise ValueError("An immutable TibiaMaps commit already exists with different content")
                shutil.rmtree(temporary)
            else:
                os.replace(temporary, destination)
            return self._renormalize_destination(destination)
        except Exception:
            self.db.rollback()
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            raise

    def renormalize_dataset(self, *, upstream_commit: str) -> dict:
        """Rebuild normalized rows from a stored commit without provider access."""
        upstream_commit = self._validate_commit(upstream_commit)
        destination = _inside(
            self.storage_root, self.storage_root / PROVIDER.replace("/", "-") / upstream_commit,
        )
        if not destination.is_dir():
            raise ValueError("Stored TibiaMaps commit is unavailable")
        try:
            return self._renormalize_destination(destination)
        except Exception:
            self.db.rollback()
            raise

    def reconcile_marker_resolutions(self, normalized_names: set[str] | None = None) -> dict[str, int]:
        """Re-resolve current stored markers after canonical identities change.

        Resolution remains exact-only. A newly introduced collision deliberately
        moves an earlier match to ``ambiguous`` instead of retaining a guess.
        The caller owns the surrounding transaction.
        """
        names = {normalize_search_text(value) for value in normalized_names or set() if value}
        exact_entities = self._exact_entity_index(names or None)
        query = self.db.query(WorldMapMarker).join(
            WorldMapFloor, WorldMapMarker.floor_id == WorldMapFloor.id,
        ).filter(WorldMapFloor.is_current.is_(True))
        if names:
            query = query.filter(WorldMapMarker.normalized_description.in_(names))

        changed = resolved = ambiguous = unresolved = 0
        for marker in query.all():
            matches = exact_entities.get(marker.normalized_description, set())
            entity_id = next(iter(matches)) if len(matches) == 1 else None
            state = "resolved" if entity_id else "ambiguous" if len(matches) > 1 else "unresolved"
            method = "exact_canonical_name_or_alias" if entity_id else None
            if (
                marker.resolved_entity_id != entity_id
                or marker.resolution_state != state
                or marker.resolution_method != method
            ):
                marker.resolved_entity_id = entity_id
                marker.resolution_state = state
                marker.resolution_method = method
                changed += 1
            resolved += int(state == "resolved")
            ambiguous += int(state == "ambiguous")
            unresolved += int(state == "unresolved")
        self.db.flush()
        return {
            "changed": changed,
            "resolved": resolved,
            "ambiguous": ambiguous,
            "unresolved": unresolved,
        }

    def _renormalize_destination(self, destination: Path) -> dict:
        manifest = self._read_json(destination / "manifest.json")
        bounds = manifest.get("bounds") or {}
        imported = manifest.get("floors") or []
        marker_path = destination / "markers.json"
        if (
            manifest.get("provider") != PROVIDER
            or manifest.get("upstream_commit") != destination.name
            or _sha256(marker_path) != manifest.get("markers_sha256")
            or len(imported) != 16
        ):
            raise ValueError("Stored TibiaMaps manifest failed integrity validation")
        width, height = int(bounds["width"]), int(bounds["height"])
        min_x, min_y = int(bounds["xMin"]), int(bounds["yMin"])
        max_x, max_y = min_x + width, min_y + height
        for item in imported:
            map_path, path_path = destination / item["map_name"], destination / item["path_name"]
            if _sha256(map_path) != item["map_sha256"] or _sha256(path_path) != item["path_sha256"]:
                raise ValueError("Stored TibiaMaps floor failed integrity validation")

        self.db.query(WorldMapDataset).filter_by(provider=PROVIDER, is_current=True).update(
            {WorldMapDataset.is_current: False}, synchronize_session=False,
        )
        dataset = self.db.query(WorldMapDataset).filter_by(
            provider=PROVIDER, upstream_commit=manifest["upstream_commit"],
        ).first()
        dataset_values = {
            "upstream_url": UPSTREAM_URL, "license_name": "MIT", "attribution": ATTRIBUTION,
            "bounds": bounds, "manifest": manifest, "markers_sha256": manifest["markers_sha256"],
            "storage_path": str(destination), "is_current": True,
        }
        if dataset is None:
            dataset = WorldMapDataset(
                provider=PROVIDER, upstream_commit=manifest["upstream_commit"], **dataset_values,
            )
            self.db.add(dataset)
        else:
            for key, value in dataset_values.items():
                setattr(dataset, key, value)
        self.db.flush()

        self.db.query(WorldMapFloor).filter_by(provider=PROVIDER, is_current=True).update(
            {WorldMapFloor.is_current: False}, synchronize_session=False,
        )
        floor_records: dict[int, WorldMapFloor] = {}
        for item in imported:
            floor = int(item["floor"])
            record = self.db.query(WorldMapFloor).filter_by(
                provider=PROVIDER, upstream_commit=manifest["upstream_commit"], floor=floor,
            ).first()
            values = {
                "dataset_id": dataset.id, "upstream_url": UPSTREAM_URL, "license_name": "MIT",
                "attribution": ATTRIBUTION, "map_path": str(destination / item["map_name"]),
                "pathfinding_path": str(destination / item["path_name"]),
                "map_sha256": item["map_sha256"], "pathfinding_sha256": item["path_sha256"],
                "width": width, "height": height, "min_x": min_x, "min_y": min_y,
                "max_x": max_x, "max_y": max_y,
                "source_metadata": {"bounds": bounds, "dataset_id": dataset.id}, "is_current": True,
            }
            if record is None:
                record = WorldMapFloor(
                    provider=PROVIDER, upstream_commit=manifest["upstream_commit"], floor=floor, **values,
                )
                self.db.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)
            self.db.flush()
            floor_records[floor] = record
            self.db.query(WorldMapMarker).filter_by(floor_id=record.id).delete(synchronize_session="fetch")

        exact_entities = self._exact_entity_index()
        marker_count = resolved_count = 0
        for index, row in enumerate(self._read_json(marker_path)):
            try:
                floor, x, y = int(row["z"]), int(row["x"]), int(row["y"])
            except (KeyError, TypeError, ValueError):
                continue
            floor_record = floor_records.get(floor)
            if floor_record is None or not (min_x <= x < max_x and min_y <= y < max_y):
                continue
            description = str(row.get("description") or "").strip()
            normalized = normalize_search_text(description)
            matches = exact_entities.get(normalized, set()) if normalized else set()
            resolved = next(iter(matches)) if len(matches) == 1 else None
            state = "resolved" if resolved else "ambiguous" if len(matches) > 1 else "unresolved"
            self.db.add(WorldMapMarker(
                floor_id=floor_record.id, source_index=index, description=description,
                normalized_description=normalized, icon=str(row.get("icon") or "")[:64] or None,
                x=x, y=y, floor=floor, raw_data=row, resolved_entity_id=resolved,
                resolution_state=state,
                resolution_method="exact_canonical_name_or_alias" if resolved else None,
            ))
            marker_count += 1
            resolved_count += int(resolved is not None)
        self.db.commit()
        return {
            "provider": PROVIDER, "upstream_commit": manifest["upstream_commit"],
            "storage_path": str(destination), "dataset_id": dataset.id,
            "floor_count": len(imported), "marker_count": marker_count,
            "resolved_marker_count": resolved_count, "manifest": manifest,
            "normalization_source": "stored_immutable_dataset",
        }

    def _exact_entity_index(self, normalized_names: set[str] | None = None) -> dict[str, set]:
        index: dict[str, set] = {}
        if normalized_names is None:
            canonical_rows = self.db.query(
                KnowledgeEntity.uuid, KnowledgeEntity.canonical_name,
            ).filter(KnowledgeEntity.status == "active").all()
            canonical_values = (
                (entity_uuid, normalize_search_text(canonical_name))
                for entity_uuid, canonical_name in canonical_rows
            )
        else:
            canonical_values = self.db.query(
                KnowledgeSearchMetadata.entity_uuid, KnowledgeSearchMetadata.normalized_name,
            ).join(KnowledgeEntity, KnowledgeEntity.uuid == KnowledgeSearchMetadata.entity_uuid).filter(
                KnowledgeEntity.status == "active",
                KnowledgeSearchMetadata.normalized_name.in_(normalized_names),
            ).all()
        for entity_uuid, normalized in canonical_values:
            if normalized:
                index.setdefault(normalized, set()).add(entity_uuid)

        alias_query = self.db.query(
            KnowledgeEntityAlias.entity_uuid, KnowledgeEntityAlias.normalized_alias,
        ).join(KnowledgeEntity, KnowledgeEntity.uuid == KnowledgeEntityAlias.entity_uuid).filter(
            KnowledgeEntity.status == "active",
        )
        if normalized_names is not None:
            alias_query = alias_query.filter(KnowledgeEntityAlias.normalized_alias.in_(normalized_names))
        for entity_uuid, normalized_alias in alias_query.all():
            normalized = normalize_search_text(normalized_alias)
            if normalized:
                index.setdefault(normalized, set()).add(entity_uuid)
        return index
