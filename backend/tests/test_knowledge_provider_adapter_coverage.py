from app.knowledge.adapters import KnowledgeAdapterRegistry
from app.knowledge.providers import INITIAL_PROVIDERS
from app.services.world_map_sync_service import WorldMapSyncService


def test_declared_provider_entities_have_executable_adapter_coverage():
    registry = KnowledgeAdapterRegistry()
    for definition in INITIAL_PROVIDERS:
        classified = {entity: (root, reason) for entity, root, reason in definition.entity_execution}
        assert set(classified) == set(definition.supports_entities)
        for entity in definition.supports_entities:
            root, reason = classified[entity]
            assert reason.strip(), f"{definition.provider_id}:{entity} needs an execution reason"
            assert registry.supported_job_types(definition.provider_id, [root]), (
                f"{definition.provider_id}:{entity} advertises root {root} without an executable adapter"
            )


def test_declared_observation_and_spatial_capabilities_are_executable():
    registry = KnowledgeAdapterRegistry()
    for definition in INITIAL_PROVIDERS:
        observations = {
            capability: (root, reason)
            for capability, root, reason in definition.observation_execution
        }
        assert set(observations) == set(definition.observation_capabilities)
        for capability, (root, reason) in observations.items():
            assert reason.strip()
            assert registry.supported_job_types(definition.provider_id, [root]), (
                f"{definition.provider_id}:{capability} has no executable observation adapter"
            )
        spatial = {
            capability: (root, reason)
            for capability, root, reason in definition.spatial_execution
        }
        assert set(spatial) == set(definition.spatial_capabilities)
        for capability, (root, reason) in spatial.items():
            assert reason.strip()
            if root == "world_map_import":
                assert callable(WorldMapSyncService.import_directory)
                assert callable(WorldMapSyncService.renormalize_dataset)
            else:
                assert registry.supported_job_types(definition.provider_id, [root])


def test_tibiawiki_hunt_zone_has_catalog_detail_and_renormalize():
    registry = KnowledgeAdapterRegistry()
    assert registry.supported_job_types("tibiawiki", ["hunt_zone"]) == [
        "hunt_zone_catalog", "hunt_zone_detail", "hunt_zone_renormalize",
    ]


def test_tibiawiki_declared_entities_are_covered_by_typed_root_adapters():
    definitions = {definition.provider_id: definition for definition in INITIAL_PROVIDERS}
    projected = {
        "creature": {"creature", "boss"},
        "item": {"item"},
        "quest": {"quest", "mission", "access"},
        "npc": {"npc"},
        "location": {"location", "area", "town"},
        "route": {"route"},
        "hunt_zone": {"hunt_zone"},
    }
    registry = KnowledgeAdapterRegistry()
    assert set().union(*projected.values()) == set(definitions["tibiawiki"].supports_entities)
    for root in projected:
        assert f"{root}_catalog" in registry.supported_job_types("tibiawiki", [root])
