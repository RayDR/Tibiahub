"""Provider-neutral knowledge transfer objects."""

from app.knowledge.dto.creature import CreatureKnowledgeDTO, CreatureLootReference
from app.knowledge.dto.item import ItemCreatureReference, ItemKnowledgeDTO, ItemNpcReference
from app.knowledge.dto.quest import (
    QuestAccessReference, QuestItemReference, QuestKnowledgeDTO, QuestMissionDTO, QuestNamedReference,
)
from app.knowledge.dto.npc_location import (
    LocationKnowledgeDTO, NamedKnowledgeReference, NpcKnowledgeDTO, NpcTradeReference,
)
from app.knowledge.dto.spatial import MapPointDTO, MapRegionDTO, RouteDTO, RouteStepDTO
from app.knowledge.dto.hunt_zone import HuntVocationRecommendation, HuntZoneKnowledgeDTO

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
    "MapPointDTO",
    "MapRegionDTO",
    "RouteDTO",
    "RouteStepDTO",
    "HuntVocationRecommendation",
    "HuntZoneKnowledgeDTO",
]
