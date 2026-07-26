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
  knowledge_entity_id?: string | null;
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
  creature_id?: number | null;
  creature_name: string;
  creature_slug?: string;
  chance?: number | null;
  rarity?: string | null;
  hunt_zones: HuntZoneSimple[];
  relationship_id?: string | null;
  knowledge_entity_id?: string | null;
  resolution_status?: 'resolved' | 'unresolved' | 'ambiguous' | null;
  source_provider?: string | null;
}

export interface ItemSearchResult {
  id?: number | null;
  image_item_id?: number | null;
  item_name: string;
  normalized_name: string;
  item_image_url?: string | null;
  source_url?: string | null;
  knowledge_entity_id?: string | null;
  item_type?: string | null;
  category?: string | null;
  data_version: number;
  last_synced_at?: string | null;
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
  knowledge_entity_id?: string | null;
  data_version: number;
  last_synced_at?: string | null;
  game_item_id?: number | null;
  item_class?: string | null;
  item_type?: string | null;
  category?: string | null;
  weight?: number | null;
  value?: number | null;
  level_requirement?: number | null;
  vocation_requirements: string[];
  attack?: number | null;
  defense?: number | null;
  armor?: number | null;
  range?: number | null;
  slots: string[];
  imbuement_slots?: number | null;
  attributes: Record<string, unknown>;
  resistances: Record<string, unknown>;
  bonuses: Record<string, unknown>;
  description?: string | null;
  notes?: string | null;
  buy_from: Record<string, unknown>[];
  sell_to: Record<string, unknown>[];
  rewards_from: string[];
  required_for: string[];
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
  category?: string;
  quest_type?: string;
  premium_required?: boolean;
  repeatable?: boolean;
  last_synced_at?: string;
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
  knowledge_entity_id?: string;
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
  summary?: string;
  image_url?: string;
  quest_type?: string;
  category?: string;
  difficulty?: string;
  duration?: string;
  premium_required?: boolean;
  repeatable?: boolean;
  solo_possible?: boolean;
  data_version: number;
  last_synced_at?: string;
  starting_npcs: QuestNamedValue[];
  related_npcs: QuestNamedValue[];
  required_items: QuestItemValue[];
  rewarded_items: QuestItemValue[];
  required_quests: QuestNamedValue[];
  unlocked_quests: QuestNamedValue[];
  required_creatures: QuestNamedValue[];
  bosses: QuestNamedValue[];
  locations: QuestNamedValue[];
  access_unlocks: Array<{ name: string; description?: string; destination_name?: string }>;
  missions: QuestMission[];
  relationships: QuestRelationship[];
}

export interface QuestNamedValue { name: string; external_id?: string; }
export interface QuestItemValue extends QuestNamedValue { amount: number; note?: string; }
export interface QuestMission {
  id: string; external_id?: string; title: string; sequence: number; description?: string;
  objectives: string[]; required_items: QuestItemValue[]; rewarded_items: QuestItemValue[];
  related_npcs: QuestNamedValue[]; related_creatures: QuestNamedValue[]; locations: QuestNamedValue[];
}
export interface QuestRelationship {
  relation_type: string; target_entity_type: string; target_name: string;
  resolution_status: 'resolved' | 'unresolved' | 'ambiguous'; target_slug?: string; mission_id?: string;
}

export interface NamedKnowledgeRelationship {
  relationship_type: string;
  target_name: string;
  target_type: string;
  target_slug?: string;
  resolution_state: 'resolved' | 'unresolved' | 'ambiguous';
}

export interface NamedKnowledgeSummary {
  id: number;
  name: string;
  slug: string;
  knowledge_entity_id: string;
  entity_type: 'npc' | 'location' | 'area' | 'town';
  description?: string;
  image_url?: string;
  source_url?: string;
  data_version: number;
  last_synced_at?: string;
}

export interface NpcKnowledgeDetail extends NamedKnowledgeSummary {
  title?: string;
  occupation?: string;
  sex?: string;
  location_name?: string;
  buys: QuestNamedValue[];
  sells: QuestNamedValue[];
  destinations: QuestNamedValue[];
  related_quests: QuestNamedValue[];
  relationships: NamedKnowledgeRelationship[];
}

export interface LocationKnowledgeDetail extends NamedKnowledgeSummary {
  location_kind?: string;
  region?: string;
  parent_location?: string;
  premium_required?: boolean;
  minimum_level?: number;
  maximum_level?: number;
  npcs: QuestNamedValue[];
  creatures: QuestNamedValue[];
  quests: QuestNamedValue[];
  sublocations: QuestNamedValue[];
  access_notes?: string;
  relationships: NamedKnowledgeRelationship[];
}

export interface SpatialPointMetadata {
  id: string; name: string; x?: number; y?: number; z?: number;
  confidence: string; verification_state: string;
}

export interface SpatialRegionMetadata {
  id: string; name: string;
  bounds: { min_x?: number; min_y?: number; max_x?: number; max_y?: number; min_z?: number; max_z?: number };
  confidence: string; verification_state: string;
}

export interface SpatialRouteStep {
  id: string; sequence: number; kind: string; instruction?: string; location_name?: string;
  x?: number; y?: number; z?: number;
}

export interface SpatialRouteMetadata {
  id: string; name: string; slug: string; step_count: number;
  start_location?: string; end_location?: string; confidence: string; verification_state: string;
  map_images?: string[];
  steps?: SpatialRouteStep[];
}

export interface HuntRecommendation {
  zone: HuntZone;
  score: number;
  reasons: string[];
  creatures: CreatureSimple[];
}

export type Vocation = 'knight' | 'paladin' | 'sorcerer' | 'druid' | 'monk';
export type Difficulty = 'Trivial' | 'Easy' | 'Medium' | 'Hard' | 'Extreme';
