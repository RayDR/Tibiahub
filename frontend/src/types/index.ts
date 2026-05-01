// Type definitions for Tibia Bestiary API

export interface Element {
  id: number;
  name: string;
  icon_url?: string;
  color?: string;
}

export interface Loot {
  id: number;
  creature_id: number;
  item_name: string;
  rarity?: string;
  percentage?: number;
  min_amount: number;
  max_amount: number;
  item_value?: number;
  item_type?: string;
}

export interface LootWithCreature extends Loot {
  creature: CreatureSimple;
}

export interface HuntZoneSimple {
  id: number;
  name: string;
  city?: string;
  min_level: number;
  max_level?: number;
  difficulty?: string;
  avg_exp_hour?: number;
  avg_profit_hour?: number;
}

export interface SpawnLocation {
  id: number;
  creature_id: number;
  hunt_zone_id: number;
  quantity?: string;
  notes?: string;
  hunt_zone?: HuntZoneSimple;
}

export interface CreatureSimple {
  id: number;
  name: string;
  hitpoints: number;
  experience: number;
  difficulty?: string;
  image_url?: string;
}

export interface Creature {
  id: number;
  name: string;
  article?: string;
  plural?: string;
  hitpoints: number;
  experience: number;
  armor: number;
  speed: number;
  max_damage?: number;
  summon_cost: number;
  convince_cost: number;
  difficulty?: string;
  occurrence?: string;
  is_boss: boolean;
  loot_value?: number;
  description?: string;
  behavior?: string;
  image_url?: string;
  loot_items: Loot[];
  spawn_locations: SpawnLocation[];
  weaknesses: Element[];
  resistances: Element[];
}

export interface HuntZone {
  id: number;
  name: string;
  city?: string;
  min_level: number;
  max_level?: number;
  recommended_level?: number;
  knights_recommended: boolean;
  paladins_recommended: boolean;
  sorcerers_recommended: boolean;
  druids_recommended: boolean;
  monks_recommended: boolean;  // Winter Update 2025
  size?: string;
  difficulty?: string;
  avg_exp_hour?: number;
  avg_profit_hour?: number;
  requires_quest: boolean;
  quest_name?: string;
  requires_premium: boolean;
  description?: string;
  tips?: string;
  location_x?: number;
  location_y?: number;
  location_z?: number;
  map_image_url?: string;

}

export interface HuntRecommendation {
  zone: HuntZone;
  score: number;
  reasons: string[];
  creatures: CreatureSimple[];
}

export type Vocation = 'knight' | 'paladin' | 'sorcerer' | 'druid' | 'monk';
export type Difficulty = 'Trivial' | 'Easy' | 'Medium' | 'Hard' | 'Extreme';
