from app.knowledge.models import KnowledgeJob, KnowledgeProvider
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.services.bootstrap import (
    KNOWLEDGE_FULL_SYNC_ROOTS,
    KnowledgeBootstrapService,
    KnowledgeFullSyncService,
    TIBIAWIKI_BOOTSTRAP_CONFIRMATION,
    TIBIAWIKI_ROOT_CATALOG_PRIORITY,
)
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


def _registry(db):
    EntityTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


def test_tibiawiki_bootstrap_requires_exact_confirmation(db):
    admin = make_user(db, username="bootstrap-admin", is_superuser=True)
    _registry(db)

    try:
        KnowledgeBootstrapService.activate_tibiawiki(
            db, actor_id=admin.id, confirmation="yes", batch_limit=50,
        )
    except ValueError as exc:
        assert str(exc) == "bootstrap_confirmation_required"
    else:
        raise AssertionError("unsafe bootstrap confirmation was accepted")

    assert db.get(KnowledgeProvider, "tibiawiki").enabled is False
    assert db.query(KnowledgeJob).count() == 0


def test_tibiawiki_bootstrap_enables_provider_and_queues_idempotent_catalog_roots(db):
    admin = make_user(db, username="bootstrap-admin-2", is_superuser=True)
    _registry(db)

    first = KnowledgeBootstrapService.activate_tibiawiki(
        db,
        actor_id=admin.id,
        confirmation=TIBIAWIKI_BOOTSTRAP_CONFIRMATION,
        batch_limit=50,
    )
    second = KnowledgeBootstrapService.activate_tibiawiki(
        db,
        actor_id=admin.id,
        confirmation=TIBIAWIKI_BOOTSTRAP_CONFIRMATION,
        batch_limit=50,
    )

    assert first.provider.enabled is True
    assert first.provider.health == "unknown"
    assert first.created_count == 7
    assert second.created_count == 0
    assert {job.entity_type_id for job in first.jobs} == {
        "creature", "item", "quest", "npc", "location", "route", "hunt_zone",
    }
    assert all(job.trigger == "bootstrap" and job.scope == {"batch_limit": 50} for job in first.jobs)
    assert all(job.priority == TIBIAWIKI_ROOT_CATALOG_PRIORITY for job in first.jobs)
    assert db.query(KnowledgeJob).count() == 7
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_tibiawiki_bootstrap_started").count() == 2


def test_full_sync_has_deterministic_executable_provider_roots_and_is_idempotent(db):
    _registry(db)
    assert [(root.provider_id, root.entity_type, root.job_type) for root in KNOWLEDGE_FULL_SYNC_ROOTS] == [
        ("tibiawiki", "creature", "creature_catalog"),
        ("tibiawiki", "item", "item_catalog"),
        ("tibiawiki", "quest", "quest_catalog"),
        ("tibiawiki", "npc", "npc_catalog"),
        ("tibiawiki", "location", "location_catalog"),
        ("tibiawiki", "route", "route_catalog"),
        ("tibiawiki", "hunt_zone", "hunt_zone_catalog"),
        ("tibiadata", "world", "world_catalog"),
        ("tibiadata", "creature", "creature_catalog"),
        ("tibiadata", "spell", "spell_catalog"),
        ("tibiadata", "boss", "boosted_bosses_current"),
    ]
    first = KnowledgeFullSyncService.enqueue(db, batch_limit=25, enable_provider_ids={"tibiawiki"})
    assert "hunt_zone" in db.get(KnowledgeProvider, "tibiawiki").supports_entities
    second = KnowledgeFullSyncService.enqueue(db, batch_limit=25, enable_provider_ids={"tibiawiki"})
    assert first.created_count == 11
    assert second.created_count == 0
    assert len(second.jobs) == 11
    assert second.skipped_count == 11
    assert {job.provider_id for job in first.jobs} == {"tibiawiki", "tibiadata"}

    for job in first.jobs:
        job.state = "succeeded"
    db.flush()
    refreshed = KnowledgeFullSyncService.enqueue(db, batch_limit=25, enable_provider_ids={"tibiawiki"})
    assert refreshed.created_count == 11
    assert all(job.trigger == "manual" for job in refreshed.jobs)

    for job in refreshed.jobs:
        job.state = "succeeded"
    db.flush()
    repaired = KnowledgeFullSyncService.enqueue(
        db, batch_limit=25, repair_existing=True, enable_provider_ids={"tibiawiki"},
    )
    assert repaired.created_count == 11
    assert all(job.trigger == "retry" for job in repaired.jobs)
