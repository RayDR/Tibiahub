// Type definitions for Tibia Bestiary API

export interface Element {
  id: number;
  name: string;
  icon_url?: string;
  color?: string;
}

export interface Loot {
  id: number;
  creature_id?: number;
  item_name: string;
  rarity?: string;
  percentage?: number | null;
  min_amount: number;
  max_amount: number;
  item_value?: number;
  item_type?: string;
  item_image_url?: string;
  source_url?: string;
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
  slug?: string;
  name: string;
  hitpoints: number;
  experience: number;
  is_boss: boolean;
  is_hidden?: boolean;
  difficulty?: string;
  classification?: string;
  image_alias?: string;
  image_url_override?: string;
  image_source_name?: string;
  image_locked?: boolean;
  related_tasks?: string[];
  image_url?: string;
  source_url?: string;
}

export interface Creature {
  id: number;
  slug?: string;
  name: string;
  article?: string;
  plural?: string;
  hitpoints: number;
  experience: number;
  armor: number;
  speed: number;
  max_damage?: number;
  summon_cost?: number | null;
  convince_cost?: number | null;
  difficulty?: string;
  occurrence?: string;
  is_boss: boolean;
  is_hidden?: boolean;
  loot_value?: number;
  description?: string;
  behavior?: string;
  image_url?: string;
  image_alias?: string;
  image_url_override?: string;
  image_source_name?: string;
  image_locked?: boolean;
  bestiary_class?: string;
  bestiary_level?: string;
  charm_points?: number | null;
  classification?: string;
  creature_class?: string;
  primary_type?: string;
  source_url?: string;
  data_sources?: string[] | null;
  missing_fields?: string[] | null;
  related_tasks?: string[] | null;
  locations?: string[] | null;
  loot_items: Loot[];
  spawn_locations: SpawnLocation[];
  weaknesses: Element[];
  resistances: Element[];
}

export interface HuntZone {
  id: number;
  name: string;
  slug?: string;
  city?: string;
  region?: string;
  min_level: number;
  max_level?: number;
  recommended_level?: number;
  recommended_vocations?: string[];
  recommended_party_size?: string;
  exp_rating?: string;
  profit_rating?: string;
  danger_rating?: string;
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
  map_x?: number;
  map_y?: number;
  map_z?: number;
  map_bounds?: Record<string, unknown>;
  map_asset_id?: number;
  map_image_url?: string;
  source_provider?: string;
  source_name?: string;
  source_url?: string;
  creatures?: CreatureSimple[];
  last_synced_at?: string;
}

export interface ItemDropCreature {
  creature_id: number;
  creature_name: string;
  creature_slug?: string;
  chance?: number | null;
  rarity?: string | null;
  hunt_zones: HuntZoneSimple[];
}

export interface ItemSearchResult {
  image_item_id?: number | null;
  item_name: string;
  normalized_name: string;
  item_image_url?: string | null;
  source_url?: string | null;
  drops: ItemDropCreature[];
}

export interface ItemDetail {
  id: number;
  item_name: string;
  normalized_name: string;
  item_image_url?: string | null;
  source_url?: string | null;
  rarity?: string | null;
  drop_chance?: number | null;
  drops: ItemDropCreature[];
}

export interface QuestSearchResult {
  id?: number;
  name: string;
  slug?: string;
  description?: string;
  group_name?: string;
  parent_page?: string;
  is_group?: boolean;
  min_level?: number;
  max_level?: number;
  experience_reward?: number;
  location?: string;
  npc?: string;
  source_url?: string;
}

export interface QuestRelatedCreature {
  creature_id: number;
  creature_name: string;
  creature_slug?: string;
  is_boss: boolean;
  classification?: string;
  image_url?: string;
}

export interface QuestDetail {
  id: number;
  name: string;
  slug?: string;
  description?: string;
  group_name?: string;
  parent_page?: string;
  is_group?: boolean;
  min_level?: number;
  max_level?: number;
  experience_reward?: number;
  location?: string;
  npc?: string;
  source_url?: string;
  rewards?: string[];
  requirements: string[];
  related_quest_names?: string[];
  related_creatures: QuestRelatedCreature[];
}

export interface HuntRecommendation {
  zone: HuntZone;
  score: number;
  reasons: string[];
  creatures: CreatureSimple[];
}

export type Vocation = 'knight' | 'paladin' | 'sorcerer' | 'druid' | 'monk';
export type Difficulty = 'Trivial' | 'Easy' | 'Medium' | 'Hard' | 'Extreme';
