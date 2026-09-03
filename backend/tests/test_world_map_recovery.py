import json
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.knowledge.metadata import refresh_search_metadata
from app.models.hunt_zone import HuntZone
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType
from app.models.world_map import WorldMapDataset, WorldMapMarker
from app.services.world_map_sync_service import WorldMapSyncService


def _source(root: Path) -> Path:
    source = root / "source"; data = source / "data"; data.mkdir(parents=True)
    (source / "LICENSE-MIT.txt").write_text("MIT fixture", encoding="utf-8")
    (data / "bounds.json").write_text(json.dumps({"floorIDs": list(range(16)), "width": 2560, "height": 2048, "xMin": 31744, "yMin": 30976}), encoding="utf-8")
    (data / "markers.json").write_text(json.dumps([
        {"x": 32728, "y": 32875, "z": 7, "description": "To Iksupan", "icon": "arrowup"},
        {"x": 34038, "y": 31726, "z": 10, "description": "Iksupan Undercity", "icon": "star"},
        {"x": 34039, "y": 31727, "z": 10, "description": "Iksupan", "icon": "star"},
        {"x": 32369, "y": 32241, "z": 7, "description": "Thais", "icon": "flag"},
    ]), encoding="utf-8")
    for floor in range(16):
        Image.new("RGB", (2560, 2048), (floor, 20, 40)).save(data / f"floor-{floor:02d}-map.png")
        Image.new("RGB", (2560, 2048), (255, 255, 255)).save(data / f"floor-{floor:02d}-path.png")
    return source


def test_local_import_bootstrap_exact_hunt_and_no_runtime_provider_request(client, db, tmp_path, monkeypatch):
    storage = tmp_path / "world-maps"; source = _source(tmp_path)
    db.add_all([
        KnowledgeEntityType(entity_type="town", display_name="Town"),
        KnowledgeEntityType(entity_type="hunt_zone", display_name="Hunt Zone"),
    ]); db.flush()
    thais = KnowledgeEntity(entity_type="town", canonical_name="Thais", slug="thais", language_neutral_id="town:test:thais")
    iksupan = KnowledgeEntity(entity_type="hunt_zone", canonical_name="Iksupan", slug="iksupan", language_neutral_id="hunt:test:iksupan")
    db.add_all([thais, iksupan]); db.flush()
    result = WorldMapSyncService(db, storage).import_directory(source, upstream_commit="d" * 40)
    assert result["floor_count"] == 16 and result["marker_count"] == 4
    manifest = Path(result["storage_path"]) / "manifest.json"
    assert manifest.is_file() and result["manifest"]["floors"][7]["map_sha256"]
    monkeypatch.setattr(settings, "WORLD_MAP_STORAGE_ROOT", str(storage))
    zone = HuntZone(name="Iksupan", normalized_name="iksupan", slug="iksupan", min_level=1, knowledge_entity_id=iksupan.uuid)
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
    assert (search["x"], search["y"], search["z"]) == (34039, 31727, 10)
    assert search["marker_label"] == "Iksupan"
    detail_map = client.get(f"/api/v1/spatial/entities/{iksupan.uuid}")
    assert detail_map.status_code == 200
    point = detail_map.json()["items"][0]["map_point"]
    assert (point["x"], point["y"], point["z"]) == (34039, 31727, 10)
    assert point["provider_metadata"]["representation_type"] == "world_map_marker"


def test_tibiamaps_stored_dataset_renormalizes_and_only_exact_names_link(db, tmp_path):
    entity_type = KnowledgeEntityType(entity_type="town", display_name="Town")
    db.add(entity_type); db.flush()
    thais = KnowledgeEntity(
        entity_type="town", canonical_name="Thais", slug="thais", language_neutral_id="town:test:thais",
    )
    db.add(thais); db.flush()
    storage, source = tmp_path / "world-maps", _source(tmp_path)
    service = WorldMapSyncService(db, storage)
    imported = service.import_directory(source, upstream_commit="e" * 40)
    dataset_id = imported["dataset_id"]
    markers = db.query(WorldMapMarker).all()
    exact = next(row for row in markers if row.description == "Thais")
    similar = next(row for row in markers if row.description == "Iksupan Undercity")
    assert exact.resolved_entity_id == thais.uuid
    assert exact.resolution_method == "exact_canonical_name_or_alias"
    assert similar.resolved_entity_id is None

    replayed = service.renormalize_dataset(upstream_commit="e" * 40)
    assert replayed["normalization_source"] == "stored_immutable_dataset"
    assert replayed["dataset_id"] == dataset_id
    assert db.query(WorldMapDataset).filter_by(is_current=True).one().upstream_commit == "e" * 40
    assert db.query(WorldMapMarker).count() == 4


def test_marker_resolution_reconciles_late_entities_and_preserves_ambiguity(db, tmp_path):
    db.add_all([
        KnowledgeEntityType(entity_type="town", display_name="Town"),
        KnowledgeEntityType(entity_type="hunt_zone", display_name="Hunt Zone"),
    ])
    db.flush()
    service = WorldMapSyncService(db, tmp_path / "world-maps")
    service.import_directory(_source(tmp_path), upstream_commit="f" * 40)
    iksupan_marker = db.query(WorldMapMarker).filter_by(description="Iksupan").one()
    assert iksupan_marker.resolution_state == "unresolved"

    zone = KnowledgeEntity(
        entity_type="hunt_zone", canonical_name="Iksupan", slug="iksupan",
        language_neutral_id="hunt:test:late-iksupan",
    )
    db.add(zone)
    refresh_search_metadata(zone)
    db.flush()
    first = service.reconcile_marker_resolutions({"iksupan"})
    assert first["changed"] == 1
    assert iksupan_marker.resolved_entity_id == zone.uuid
    assert iksupan_marker.resolution_state == "resolved"

    town = KnowledgeEntity(
        entity_type="town", canonical_name="Iksupan", slug="iksupan-town",
        language_neutral_id="town:test:late-iksupan",
    )
    db.add(town)
    refresh_search_metadata(town)
    db.flush()
    second = service.reconcile_marker_resolutions({"iksupan"})
    assert second["changed"] == 1
    assert iksupan_marker.resolved_entity_id is None
    assert iksupan_marker.resolution_state == "ambiguous"
