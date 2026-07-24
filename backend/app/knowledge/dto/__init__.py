"""Provider-neutral knowledge transfer objects."""

from app.knowledge.dto.creature import CreatureKnowledgeDTO, CreatureLootReference
from app.knowledge.dto.item import ItemCreatureReference, ItemKnowledgeDTO, ItemNpcReference

__all__ = [
    "CreatureKnowledgeDTO",
    "CreatureLootReference",
    "ItemKnowledgeDTO",
    "ItemNpcReference",
    "ItemCreatureReference",
]
