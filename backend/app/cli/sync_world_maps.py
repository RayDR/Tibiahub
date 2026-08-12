"""Download (sync-time only) or import a staged TibiaMaps checkout."""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.world_map_sync_service import UPSTREAM_URL, WorldMapSyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache TibiaMaps world floors locally")
    parser.add_argument("--source-dir", help="Existing tibiamaps/tibia-map-data checkout; avoids network access")
    parser.add_argument("--commit", help="Required for a non-git staged source directory")
    parser.add_argument("--storage-root", default=settings.WORLD_MAP_STORAGE_ROOT)
    args = parser.parse_args()

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.source_dir:
        source = Path(args.source_dir).resolve()
    else:
        temporary = tempfile.TemporaryDirectory(prefix="tibiahub-world-map-sync-")
        source = Path(temporary.name) / "tibia-map-data"
        subprocess.run(["git", "clone", "--depth", "1", UPSTREAM_URL, str(source)], check=True)
    commit = args.commit
    if not commit and (source / ".git").exists():
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    if not commit:
        raise SystemExit("--commit is required when --source-dir is not a git checkout")

    with SessionLocal() as db:
        result = WorldMapSyncService(db, args.storage_root).import_directory(source, upstream_commit=commit)
    print(f"Imported {result['floor_count']} floors and {result['marker_count']} markers at {result['upstream_commit']}")
    if temporary:
        temporary.cleanup()


if __name__ == "__main__":
    main()
