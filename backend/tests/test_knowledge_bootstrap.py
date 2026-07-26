from app.knowledge.models import KnowledgeJob, KnowledgeProvider
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.services.bootstrap import (
    KnowledgeBootstrapService,
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
    assert first.created_count == 6
    assert second.created_count == 0
    assert {job.entity_type_id for job in first.jobs} == {"creature", "item", "quest", "npc", "location", "route"}
    assert all(job.trigger == "bootstrap" and job.scope == {"batch_limit": 50} for job in first.jobs)
    assert all(job.priority == TIBIAWIKI_ROOT_CATALOG_PRIORITY for job in first.jobs)
    assert db.query(KnowledgeJob).count() == 6
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_tibiawiki_bootstrap_started").count() == 2
