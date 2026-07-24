from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.knowledge.models import KnowledgeRelationship, KnowledgeRelationshipType
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService, KnowledgeGraphService, RelationshipInput
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


@pytest.fixture
def graph_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)


def entity(db, entity_type: str, name: str):
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type, canonical_name=name,
        language_neutral_id=f"{entity_type}:{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
    ))


def test_registry_has_directional_inverse_and_rejects_invalid_pairs(db, graph_registry):
    drops = db.get(KnowledgeRelationshipType, "drops")
    assert drops.inverse_code == "dropped_by"
    assert RelationshipTypeRegistry.inverse(db, "dropped_by") == "drops"
    RelationshipTypeRegistry.validate(db, "drops", "creature", "item")
    with pytest.raises(ValueError):
        RelationshipTypeRegistry.validate(db, "drops", "quest", "item")
    assert RelationshipTypeRegistry.verify_integrity(db) == []


def test_future_symmetric_type_uses_one_row_and_same_inverse(db, graph_registry):
    db.add(KnowledgeRelationshipType(
        code="related_to", display_translation_key="knowledgeGraph.relationships.related_to",
        inverse_code="related_to", source_entity_types=["creature"], target_entity_types=["creature"],
        directional=False, symmetric=True, transitive=False, user_visible=False, ai_visible=True, active=True,
    ))
    left = entity(db, "creature", "Symmetric Left")
    right = entity(db, "creature", "Symmetric Right")
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=left.uuid, relationship_type="related_to", target_entity_id=right.uuid,
    ))
    assert KnowledgeGraphService.outgoing(db, left.uuid)[0].relationship_type == "related_to"
    assert KnowledgeGraphService.incoming(db, right.uuid)[0].relationship_type == "related_to"
    assert db.query(KnowledgeRelationship).filter_by(relationship_type_code="related_to").count() == 1


def test_graph_deduplicates_provenance_and_derives_incoming_inverse(db, graph_registry):
    creature = entity(db, "creature", "Demon")
    item = entity(db, "item", "Demon Horn")
    value = RelationshipInput(
        source_entity_id=creature.uuid, relationship_type="drops", target_entity_id=item.uuid,
        source_provider_id="tibiawiki", confidence="high",
    )
    first = KnowledgeGraphService.upsert(db, value)
    second = KnowledgeGraphService.upsert(db, value)
    assert first.created is True and second.created is False
    assert db.query(KnowledgeRelationship).count() == 1
    outgoing = KnowledgeGraphService.outgoing(db, creature.uuid)
    incoming = KnowledgeGraphService.incoming(db, item.uuid)
    assert [(row.relationship_type, row.target_name) for row in outgoing] == [("drops", "Demon Horn")]
    assert [(row.relationship_type, row.target_name) for row in incoming] == [("dropped_by", "Demon")]


def test_provenance_consolidation_manual_precedence_and_provider_reconciliation(db, graph_registry):
    quest = entity(db, "quest", "The Test Quest")
    item = entity(db, "item", "Test Key")
    for provider in ("tibiawiki", "tibiadata"):
        KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=quest.uuid, relationship_type="requires_item", target_entity_id=item.uuid,
            source_provider_id=provider, confidence="medium",
        ))
    manual = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="requires_item", target_entity_id=item.uuid,
        confidence="verified", manual_override=True, verified_by_id=None,
    ))
    consolidated = KnowledgeGraphService.outgoing(db, quest.uuid)
    assert len(consolidated) == 1
    assert consolidated[0].provenance_count == 3
    assert consolidated[0].confidence == "verified"
    assert consolidated[0].manual_verified is True
    provider_row = db.query(KnowledgeRelationship).filter_by(source_provider_id="tibiawiki").one()
    assert KnowledgeGraphService.reconcile_provider(
        db, source_entity_id=quest.uuid, source_scope="entity", provider_id="tibiawiki",
        relationship_types={"requires_item"}, current_ids=set(),
    ) == 1
    assert provider_row.is_current is False
    assert manual.relationship.is_current is True


def test_unresolved_ambiguous_resolution_rejection_verification_and_history(db, graph_registry):
    quest = entity(db, "quest", "Graph Quest")
    item = entity(db, "item", "Graph Item")
    unresolved = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="rewards_item", target_entity_type="item",
        unresolved_name="Graph Item", resolution_state="ambiguous", confidence="low",
        source_provider_id="tibiawiki", source_context={"candidate_entity_ids": [str(item.uuid)]},
    )).relationship
    resolved = KnowledgeGraphService.resolve_reference(
        db, unresolved, item.uuid, admin_id=1, reason="Matched official item",
    )
    assert unresolved.is_current is False and unresolved.superseded_by_id == resolved.id
    assert resolved.confidence == "verified" and resolved.manual_override is True
    KnowledgeGraphService.verify(db, resolved, admin_id=1, reason="Reviewed")
    rejected = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="requires_item", target_entity_type="item",
        unresolved_name="Not an item", resolution_state="unresolved", confidence="unknown",
        source_provider_id="tibiawiki",
    )).relationship
    KnowledgeGraphService.reject(db, rejected, admin_id=1, reason="Invalid provider reference")
    assert rejected.resolution_state == "rejected" and rejected.is_current is False


def test_batch_upsert_and_consistency_report(db, graph_registry):
    creature = entity(db, "creature", "Batch Creature")
    item = entity(db, "item", "Batch Item")
    values = [RelationshipInput(source_entity_id=creature.uuid, relationship_type="drops", target_entity_id=item.uuid)] * 2
    mutations = KnowledgeGraphService.batch_upsert(db, values)
    assert [mutation.created for mutation in mutations] == [True, False]
    report = KnowledgeGraphService.verify_consistency(db)
    assert report["relationships"] == 1
    assert report["registry_errors"] == []
    assert not any(value for key, value in report.items() if key not in {"relationships", "registry_errors"})


def test_public_graph_and_admin_review_permissions_and_audit(client, db, graph_registry):
    quest = entity(db, "quest", "API Quest")
    item = entity(db, "item", "API Item")
    unresolved = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="requires_item", target_entity_type="item",
        unresolved_name="API Item", resolution_state="ambiguous", source_provider_id="tibiawiki",
        source_context={"candidate_entity_ids": [str(item.uuid)]},
    )).relationship
    db.flush()
    public = client.get(f"/api/v1/knowledge/entities/{quest.uuid}/relationships")
    assert public.status_code == 200 and public.json()["items"] == []
    user = make_user(db, username="graph_user")
    admin = make_user(db, username="graph_admin", is_superuser=True)
    user_token = create_access_token(user.username)
    admin_token = create_access_token(admin.username)
    denied = client.get("/api/v1/admin/knowledge/relationships/review", headers={"Authorization": f"Bearer {user_token}"})
    assert denied.status_code == 403
    review = client.get("/api/v1/admin/knowledge/relationships/review?resolution_state=ambiguous", headers={"Authorization": f"Bearer {admin_token}"})
    assert review.status_code == 200 and review.json()["items"][0]["candidates"][0]["id"] == str(item.uuid)
    resolved = client.post(
        f"/api/v1/admin/knowledge/relationships/{unresolved.id}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_entity_id": str(item.uuid), "reason": "Confirmed official entity"},
    )
    assert resolved.status_code == 200 and resolved.json()["resolution_state"] == "resolved"
    outgoing = client.get(
        f"/api/v1/knowledge/entities/{quest.uuid}/relationships/outgoing",
        params={"relationship_type": "requires_item", "skip": 0, "limit": 1},
    )
    incoming = client.get(
        f"/api/v1/knowledge/entities/{item.uuid}/relationships/incoming",
        params={"relationship_type": "required_by_quest"},
    )
    assert outgoing.status_code == 200 and outgoing.json()["total"] == 1
    assert incoming.status_code == 200 and incoming.json()["items"][0]["target_name"] == "API Quest"
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_relationship_resolved").count() == 1
