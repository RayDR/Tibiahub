"""Canonical entity lifecycle services."""

from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
    UnknownEntityTypeError,
)
from app.knowledge.services.jobs import (
    CompletedJobRecreationError,
    EnqueueKnowledgeJob,
    EnqueueResult,
    KnowledgeJobConflictError,
    KnowledgeJobNotFoundError,
    KnowledgeJobOwnershipError,
    KnowledgeJobService,
    ProviderUnavailableForJobError,
)
from app.knowledge.services.creature_normalization import (
    CreatureIdentityConflictError,
    CreatureKnowledgeNormalizationService,
)
from app.knowledge.services.item_normalization import (
    ItemIdentityConflictError,
    ItemKnowledgeNormalizationService,
    ItemNormalizationApplied,
)
from app.knowledge.services.quest_normalization import (
    QuestIdentityConflictError,
    QuestKnowledgeNormalizationService,
)
from app.knowledge.services.graph import (
    ConsolidatedRelationship,
    KnowledgeGraphService,
    RelationshipInput,
    RelationshipMutation,
)
from app.knowledge.services.item_relationships import (
    DropRelationshipResult,
    link_creature_loot,
    link_item_drops,
    upsert_drop_relationship,
)
from app.knowledge.services.reconciliation import (
    ExactReferenceReport,
    ProvenanceRepairReport,
    reconcile_exact_references,
    repair_document_provenance,
)
from app.knowledge.services.spatial import (
    PostGISUnavailableError,
    entities_inside_region,
    link_entity_to_location,
    nearby_entities,
    persist_map_point,
    persist_map_region,
    persist_route,
    postgis_status,
)

__all__ = [
    "DuplicateKnowledgeAliasError",
    "DuplicateKnowledgeEntityError",
    "KnowledgeEntityService",
    "UnknownEntityTypeError",
    "CompletedJobRecreationError",
    "EnqueueKnowledgeJob",
    "EnqueueResult",
    "KnowledgeJobConflictError",
    "KnowledgeJobNotFoundError",
    "KnowledgeJobOwnershipError",
    "KnowledgeJobService",
    "ProviderUnavailableForJobError",
    "CreatureIdentityConflictError",
    "CreatureKnowledgeNormalizationService",
    "ItemIdentityConflictError",
    "ItemKnowledgeNormalizationService",
    "QuestIdentityConflictError",
    "QuestKnowledgeNormalizationService",
    "ConsolidatedRelationship",
    "KnowledgeGraphService",
    "RelationshipInput",
    "RelationshipMutation",
    "ItemNormalizationApplied",
    "DropRelationshipResult",
    "link_creature_loot",
    "link_item_drops",
    "upsert_drop_relationship",
    "ExactReferenceReport",
    "ProvenanceRepairReport",
    "reconcile_exact_references",
    "repair_document_provenance",
    "PostGISUnavailableError",
    "postgis_status",
    "persist_map_point",
    "persist_map_region",
    "persist_route",
    "link_entity_to_location",
    "nearby_entities",
    "entities_inside_region",
]
