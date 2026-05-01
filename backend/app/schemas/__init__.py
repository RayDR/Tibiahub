"""
Pydantic schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


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


class LootCreate(LootBase):
    pass



class Loot(LootBase):
    id: int
    creature_id: int
    
    class Config:
        from_attributes = True






# Hunt Zone Schemas
class HuntZoneBase(BaseModel):
    name: str
    city: Optional[str] = None
    min_level: int
    max_level: Optional[int] = None
    recommended_level: Optional[int] = None
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
    map_image_url: Optional[str] = None


class HuntZoneCreate(HuntZoneBase):
    pass


class HuntZoneSimple(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    min_level: int
    max_level: Optional[int] = None
    difficulty: Optional[str] = None
    
    class Config:
        from_attributes = True


class HuntZone(HuntZoneBase):
    id: int
    
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
    loot_value: Optional[float] = None
    description: Optional[str] = None
    behavior: Optional[str] = None
    image_url: Optional[str] = None


class CreatureCreate(CreatureBase):
    pass


class CreatureSimple(BaseModel):
    id: int
    name: str
    hitpoints: int
    experience: int
    difficulty: Optional[str] = None
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class LootWithCreature(Loot):
    creature: CreatureSimple


class Creature(CreatureBase):
    id: int
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
