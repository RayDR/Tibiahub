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
from app.knowledge.services.item_relationships import (
    DropRelationshipResult,
    link_creature_loot,
    link_item_drops,
    upsert_drop_relationship,
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
    "ItemNormalizationApplied",
    "DropRelationshipResult",
    "link_creature_loot",
    "link_item_drops",
    "upsert_drop_relationship",
]
