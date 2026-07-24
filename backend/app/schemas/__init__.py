"""Pydantic schemas for API validation."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime
from uuid import UUID


# Vocation Enum for Winter Update 2025
class Vocation(str, Enum):
    knight = "knight"
    paladin = "paladin"
    sorcerer = "sorcerer"
    druid = "druid"
    monk = "monk"  # NEW Winter Update 2025!


# Element Schemas
class ElementBase(BaseModel):
    name: str
    icon_url: Optional[str] = None
    color: Optional[str] = None


class ElementCreate(ElementBase):
    pass


class Element(ElementBase):
    id: int
    
    class Config:
        from_attributes = True


# Loot Schemas
class LootBase(BaseModel):
    item_name: str
    rarity: Optional[str] = None
    percentage: Optional[float] = None
    min_amount: int = 1
    max_amount: int = 1
    item_value: Optional[int] = None
    item_type: Optional[str] = None
    item_image_url: Optional[str] = None
    source_url: Optional[str] = None


class LootCreate(LootBase):
    pass



class Loot(LootBase):
    id: int
    creature_id: Optional[int] = None
    
    class Config:
        from_attributes = True






# Hunt Zone Schemas
class HuntZoneBase(BaseModel):
    name: str
    slug: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    min_level: Optional[int] = None
    max_level: Optional[int] = None
    recommended_level: Optional[int] = None
    recommended_vocations: Optional[List[str]] = None
    recommended_party_size: Optional[str] = None
    exp_rating: Optional[str] = None
    profit_rating: Optional[str] = None
    danger_rating: Optional[str] = None
    knights_recommended: bool = False
    paladins_recommended: bool = False
    sorcerers_recommended: bool = False
    druids_recommended: bool = False
    monks_recommended: bool = False  # Winter Update 2025
    size: Optional[str] = None
    difficulty: Optional[str] = None
    avg_exp_hour: Optional[int] = None
    avg_profit_hour: Optional[int] = None
    requires_quest: bool = False
    quest_name: Optional[str] = None
    requires_premium: bool = False
    description: Optional[str] = None
    tips: Optional[str] = None
    location_x: Optional[int] = None
    location_y: Optional[int] = None
    location_z: Optional[int] = None
    map_x: Optional[int] = None
    map_y: Optional[int] = None
    map_z: Optional[int] = None
    map_bounds: Optional[dict] = None
    map_image_url: Optional[str] = None
    source_url: Optional[str] = None
    source_provider: Optional[str] = None


class HuntZoneCreate(HuntZoneBase):
    pass


class HuntZoneSimple(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    min_level: Optional[int] = None
    max_level: Optional[int] = None
    difficulty: Optional[str] = None
    source_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class HuntZone(HuntZoneBase):
    id: int
    creatures: List[CreatureSimple] = []
    last_synced_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Spawn Location Schemas
class SpawnLocationBase(BaseModel):
    quantity: Optional[str] = None
    notes: Optional[str] = None


class SpawnLocationCreate(SpawnLocationBase):
    creature_id: int
    hunt_zone_id: int


class SpawnLocation(SpawnLocationBase):
    id: int
    creature_id: int
    hunt_zone_id: int
    hunt_zone: Optional[HuntZoneSimple] = None
    
    class Config:
        from_attributes = True


# Creature Schemas
class CreatureBase(BaseModel):
    name: str
    article: Optional[str] = None
    plural: Optional[str] = None
    hitpoints: int
    experience: int
    armor: int = 0
    speed: int = 0
    max_damage: Optional[int] = None
    summon_cost: Optional[int] = None
    convince_cost: Optional[int] = None
    difficulty: Optional[str] = None
    occurrence: Optional[str] = None
    is_boss: bool = False
    is_hidden: bool = False
    loot_value: Optional[float] = None
    description: Optional[str] = None
    behavior: Optional[str] = None
    image_url: Optional[str] = None
    image_alias: Optional[str] = None
    image_url_override: Optional[str] = None
    image_source_name: Optional[str] = None
    image_locked: Optional[bool] = None
    bestiary_class: Optional[str] = None
    bestiary_level: Optional[str] = None
    charm_points: Optional[int] = None
    classification: Optional[str] = None
    creature_class: Optional[str] = None
    primary_type: Optional[str] = None
    source_url: Optional[str] = None
    data_sources: Optional[List[str]] = None
    missing_fields: Optional[List[str]] = None
    related_tasks: Optional[List[str]] = None
    locations: Optional[List[str]] = None


class CreatureCreate(CreatureBase):
    pass


class CreatureSimple(BaseModel):
    id: int
    slug: Optional[str] = None
    name: str
    hitpoints: int
    experience: int
    is_boss: bool = False
    is_hidden: bool = False
    difficulty: Optional[str] = None
    classification: Optional[str] = None
    related_tasks: Optional[List[str]] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class LootWithCreature(Loot):
    creature: CreatureSimple


class Creature(CreatureBase):
    id: int
    slug: Optional[str] = None
    normalized_name: Optional[str] = None
    external_id: Optional[str] = None
    source_name: Optional[str] = None
    knowledge_entity_id: Optional[UUID] = None
    data_version: int = 1
    last_synced_at: Optional[datetime] = None
    loot_items: List[Loot] = []
    spawn_locations: List[SpawnLocation] = []
    weaknesses: List[Element] = []
    resistances: List[Element] = []
    
    class Config:
        from_attributes = True


# Hunt Recommendation Schema
class HuntRecommendation(BaseModel):
    zone: HuntZone
    score: float = Field(..., description="Recommendation score (0-100)")
    reasons: List[str] = Field(..., description="Why this zone is recommended")
    creatures: List[CreatureSimple] = Field(..., description="Main creatures in this zone")


class ItemDropCreature(BaseModel):
    creature_id: Optional[int] = None
    creature_name: str
    creature_slug: Optional[str] = None
    chance: Optional[float] = None
    rarity: Optional[str] = None
    hunt_zones: List[HuntZoneSimple] = []
    relationship_id: Optional[UUID] = None
    knowledge_entity_id: Optional[UUID] = None
    resolution_status: Optional[str] = None
    source_provider: Optional[str] = None


class ItemSearchResult(BaseModel):
    id: Optional[int] = None
    image_item_id: Optional[int] = None
    item_name: str
    normalized_name: str
    item_image_url: Optional[str] = None
    source_url: Optional[str] = None
    knowledge_entity_id: Optional[UUID] = None
    item_type: Optional[str] = None
    category: Optional[str] = None
    data_version: int = 1
    last_synced_at: Optional[datetime] = None
    drops: List[ItemDropCreature] = []


class ItemDetail(BaseModel):
    id: int
    item_name: str
    normalized_name: str
    item_image_url: Optional[str] = None
    source_url: Optional[str] = None
    rarity: Optional[str] = None
    drop_chance: Optional[float] = None
    knowledge_entity_id: Optional[UUID] = None
    data_version: int = 1
    last_synced_at: Optional[datetime] = None
    game_item_id: Optional[int] = None
    item_class: Optional[str] = None
    item_type: Optional[str] = None
    category: Optional[str] = None
    weight: Optional[float] = None
    value: Optional[int] = None
    level_requirement: Optional[int] = None
    vocation_requirements: List[str] = []
    attack: Optional[int] = None
    defense: Optional[int] = None
    armor: Optional[int] = None
    range: Optional[int] = None
    slots: List[str] = []
    imbuement_slots: Optional[int] = None
    attributes: dict = {}
    resistances: dict = {}
    bonuses: dict = {}
    description: Optional[str] = None
    notes: Optional[str] = None
    buy_from: List[dict] = []
    sell_to: List[dict] = []
    rewards_from: List[str] = []
    required_for: List[str] = []
    drops: List[ItemDropCreature] = []


class QuestSearchResult(BaseModel):
    id: Optional[int] = None
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    group_name: Optional[str] = None
    parent_page: Optional[str] = None
    is_group: bool = False
    min_level: Optional[int] = None
    max_level: Optional[int] = None
    experience_reward: Optional[int] = None
    location: Optional[str] = None
    npc: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    quest_type: Optional[str] = None
    premium_required: Optional[bool] = None
    repeatable: Optional[bool] = None
    last_synced_at: Optional[datetime] = None


class QuestRelatedCreature(BaseModel):
    creature_id: int
    creature_name: str
    creature_slug: Optional[str] = None
    is_boss: bool = False
    classification: Optional[str] = None
    image_url: Optional[str] = None


class QuestNamedValue(BaseModel):
    name: str
    external_id: Optional[str] = None


class QuestItemValue(QuestNamedValue):
    amount: int = 1
    note: Optional[str] = None


class QuestMissionResult(BaseModel):
    id: UUID
    external_id: Optional[str] = None
    title: str
    sequence: int
    description: Optional[str] = None
    objectives: List[str] = []
    required_items: List[QuestItemValue] = []
    rewarded_items: List[QuestItemValue] = []
    related_npcs: List[QuestNamedValue] = []
    related_creatures: List[QuestNamedValue] = []
    locations: List[QuestNamedValue] = []


class QuestRelationResult(BaseModel):
    relation_type: str
    target_entity_type: str
    target_name: str
    resolution_status: str
    target_slug: Optional[str] = None
    mission_id: Optional[UUID] = None


class QuestDetail(BaseModel):
    id: int
    knowledge_entity_id: Optional[UUID] = None
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    group_name: Optional[str] = None
    parent_page: Optional[str] = None
    is_group: bool = False
    min_level: Optional[int] = None
    max_level: Optional[int] = None
    experience_reward: Optional[int] = None
    location: Optional[str] = None
    npc: Optional[str] = None
    rewards: List[str] = []
    source_url: Optional[str] = None
    requirements: List[str] = []
    related_quest_names: List[str] = []
    related_creatures: List[QuestRelatedCreature] = []
    summary: Optional[str] = None
    image_url: Optional[str] = None
    quest_type: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    duration: Optional[str] = None
    premium_required: Optional[bool] = None
    repeatable: Optional[bool] = None
    solo_possible: Optional[bool] = None
    data_version: int = 1
    last_synced_at: Optional[datetime] = None
    starting_npcs: List[QuestNamedValue] = []
    related_npcs: List[QuestNamedValue] = []
    required_items: List[QuestItemValue] = []
    rewarded_items: List[QuestItemValue] = []
    required_quests: List[QuestNamedValue] = []
    unlocked_quests: List[QuestNamedValue] = []
    required_creatures: List[QuestNamedValue] = []
    bosses: List[QuestNamedValue] = []
    locations: List[QuestNamedValue] = []
    access_unlocks: List[dict] = []
    missions: List[QuestMissionResult] = []
    relationships: List[QuestRelationResult] = []


class HomeHighlights(BaseModel):
    featured_creatures: List[CreatureSimple] = []
    trending_creatures: List[CreatureSimple] = []
    featured_items: List[ItemSearchResult] = []
    trending_items: List[ItemSearchResult] = []
    featured_hunt_zones: List[HuntZoneSimple] = []
    trending_hunt_zones: List[HuntZoneSimple] = []
