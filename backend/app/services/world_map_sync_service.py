"""Explicit sync-time importer for the MIT-licensed TibiaMaps dataset.

Public request paths never call this service and never perform network I/O.
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

from app.models.world_map import WorldMapFloor, WorldMapMarker
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

    def import_directory(self, source_root: str | Path, *, upstream_commit: str) -> dict:
        if not upstream_commit or len(upstream_commit) < 7 or any(ch not in "0123456789abcdef" for ch in upstream_commit.lower()):
            raise ValueError("A hexadecimal upstream commit is required")
        source_root = Path(source_root).resolve()
        data_root = source_root / "data"
        bounds_path = data_root / "bounds.json"
        markers_path = data_root / "markers.json"
        license_path = source_root / "LICENSE-MIT.txt"
        if not bounds_path.is_file() or not markers_path.is_file() or not license_path.is_file():
            raise ValueError("Source must contain data/bounds.json, data/markers.json, and LICENSE-MIT.txt")

        bounds = json.loads(bounds_path.read_text(encoding="utf-8"))
        marker_rows = json.loads(markers_path.read_text(encoding="utf-8"))
        floors = [int(value) for value in bounds.get("floorIDs", [])]
        if floors != list(range(16)):
            raise ValueError("Expected Tibia floors 00 through 15")
        width, height = int(bounds["width"]), int(bounds["height"])
        min_x, min_y = int(bounds["xMin"]), int(bounds["yMin"])
        # Upstream bounds are inclusive tile-block starts; the generated PNG
        # includes the final 256-tile block.
        max_x, max_y = min_x + width, min_y + height

        destination = _inside(self.storage_root, self.storage_root / PROVIDER.replace("/", "-") / upstream_commit)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="world-map-import-", dir=str(destination.parent)))
        try:
            temporary.mkdir(parents=True, exist_ok=True)
            license_target = temporary / "LICENSE-MIT.txt"
            shutil.copy2(license_path, license_target)
            imported: list[dict] = []
            for floor in floors:
                map_source = data_root / f"floor-{floor:02d}-map.png"
                path_source = data_root / f"floor-{floor:02d}-path.png"
                if not map_source.is_file() or not path_source.is_file():
                    raise ValueError(f"Missing floor {floor:02d} map or pathfinding PNG")
                with Image.open(map_source) as image:
                    if image.format != "PNG" or image.size != (width, height):
                        raise ValueError(f"Unexpected floor {floor:02d} map dimensions")
                with Image.open(path_source) as image:
                    if image.format != "PNG" or image.size != (width, height):
                        raise ValueError(f"Unexpected floor {floor:02d} path dimensions")
                map_target = temporary / map_source.name
                path_target = temporary / path_source.name
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
                "license": "MIT", "attribution": ATTRIBUTION, "bounds": bounds, "floors": imported,
                "markers_sha256": _sha256(temporary / "markers.json"),
            }
            (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if destination.exists():
                shutil.rmtree(temporary)
            else:
                os.replace(temporary, destination)

            self.db.query(WorldMapFloor).filter(WorldMapFloor.provider == PROVIDER, WorldMapFloor.is_current.is_(True)).update({WorldMapFloor.is_current: False}, synchronize_session=False)
            floor_records: dict[int, WorldMapFloor] = {}
            for item in imported:
                record = self.db.query(WorldMapFloor).filter_by(provider=PROVIDER, upstream_commit=upstream_commit, floor=item["floor"]).first()
                values = {
                    "upstream_url": UPSTREAM_URL, "license_name": "MIT", "attribution": ATTRIBUTION,
                    "map_path": str(destination / item["map_name"]), "pathfinding_path": str(destination / item["path_name"]),
                    "map_sha256": item["map_sha256"], "pathfinding_sha256": item["path_sha256"],
                    "width": width, "height": height, "min_x": min_x, "min_y": min_y,
                    "max_x": max_x, "max_y": max_y, "source_metadata": {"bounds": bounds}, "is_current": True,
                }
                if record is None:
                    record = WorldMapFloor(provider=PROVIDER, upstream_commit=upstream_commit, floor=item["floor"], **values)
                    self.db.add(record)
                else:
                    for key, value in values.items():
                        setattr(record, key, value)
                self.db.flush()
                floor_records[item["floor"]] = record
                self.db.query(WorldMapMarker).filter_by(floor_id=record.id).delete(synchronize_session=False)

            marker_count = 0
            for index, row in enumerate(marker_rows):
                try:
                    floor, x, y = int(row["z"]), int(row["x"]), int(row["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                floor_record = floor_records.get(floor)
                if floor_record is None or not (min_x <= x < max_x and min_y <= y < max_y):
                    continue
                description = str(row.get("description") or "").strip()
                self.db.add(WorldMapMarker(
                    floor_id=floor_record.id, source_index=index, description=description,
                    normalized_description=normalize_search_text(description), icon=str(row.get("icon") or "")[:64] or None,
                    x=x, y=y, floor=floor, raw_data=row,
                ))
                marker_count += 1
            self.db.commit()
            return {"provider": PROVIDER, "upstream_commit": upstream_commit, "storage_path": str(destination), "floor_count": len(imported), "marker_count": marker_count, "manifest": manifest}
        except Exception:
            self.db.rollback()
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            raise
