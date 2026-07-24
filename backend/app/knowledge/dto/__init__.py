"""Provider-neutral knowledge transfer objects."""

from app.knowledge.dto.creature import CreatureKnowledgeDTO, CreatureLootReference
from app.knowledge.dto.item import ItemCreatureReference, ItemKnowledgeDTO, ItemNpcReference
from app.knowledge.dto.quest import (
    QuestAccessReference, QuestItemReference, QuestKnowledgeDTO, QuestMissionDTO, QuestNamedReference,
)
from app.knowledge.dto.npc_location import (
    LocationKnowledgeDTO, NamedKnowledgeReference, NpcKnowledgeDTO, NpcTradeReference,
)

__all__ = [
    "CreatureKnowledgeDTO",
    "CreatureLootReference",
    "ItemKnowledgeDTO",
    "ItemNpcReference",
    "ItemCreatureReference",
    "QuestAccessReference",
    "QuestItemReference",
    "QuestKnowledgeDTO",
    "QuestMissionDTO",
    "QuestNamedReference",
    "LocationKnowledgeDTO",
    "NamedKnowledgeReference",
    "NpcKnowledgeDTO",
    "NpcTradeReference",
]
