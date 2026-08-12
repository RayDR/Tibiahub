import json
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.models.hunt_zone import HuntZone
from app.services.world_map_sync_service import WorldMapSyncService


def _source(root: Path) -> Path:
    source = root / "source"; data = source / "data"; data.mkdir(parents=True)
    (source / "LICENSE-MIT.txt").write_text("MIT fixture", encoding="utf-8")
    (data / "bounds.json").write_text(json.dumps({"floorIDs": list(range(16)), "width": 2560, "height": 2048, "xMin": 31744, "yMin": 30976}), encoding="utf-8")
    (data / "markers.json").write_text(json.dumps([
        {"x": 32728, "y": 32875, "z": 7, "description": "To Iksupan", "icon": "arrowup"},
        {"x": 34038, "y": 31726, "z": 10, "description": "Iksupan Undercity", "icon": "star"},
        {"x": 32369, "y": 32241, "z": 7, "description": "Thais", "icon": "flag"},
    ]), encoding="utf-8")
    for floor in range(16):
        Image.new("RGB", (2560, 2048), (floor, 20, 40)).save(data / f"floor-{floor:02d}-map.png")
        Image.new("RGB", (2560, 2048), (255, 255, 255)).save(data / f"floor-{floor:02d}-path.png")
    return source


def test_local_import_bootstrap_exact_hunt_and_no_runtime_provider_request(client, db, tmp_path, monkeypatch):
    storage = tmp_path / "world-maps"; source = _source(tmp_path)
    result = WorldMapSyncService(db, storage).import_directory(source, upstream_commit="d" * 40)
    assert result["floor_count"] == 16 and result["marker_count"] == 3
    manifest = Path(result["storage_path"]) / "manifest.json"
    assert manifest.is_file() and result["manifest"]["floors"][7]["map_sha256"]
    monkeypatch.setattr(settings, "WORLD_MAP_STORAGE_ROOT", str(storage))
    zone = HuntZone(name="Iksupan", normalized_name="iksupan", slug="iksupan", min_level=1)
    db.add(zone); db.commit()

    # Any runtime provider request would fail this test; public routes only read DB/files.
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("external runtime request")))
    bootstrap = client.get("/api/v1/map/bootstrap", params={"floor": 7})
    assert bootstrap.status_code == 200
    assert bootstrap.json()["world_map"]["upstream_commit"] == "d" * 40
    assert bootstrap.json()["towns"][0]["name"] == "Thais"
    floor = client.get("/api/v1/map/floors/7/image")
    assert floor.status_code == 200 and floor.headers["x-map-source"] == "local-world-map-cache"
    search = client.get("/api/v1/map/search", params={"q": "Iksupan", "layers": "hunt_zone"}).json()["items"][0]
    assert (search["x"], search["y"], search["z"]) == (34038, 31726, 10)
    assert search["marker_label"] == "Iksupan Undercity"
