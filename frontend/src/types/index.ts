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
  slug?: string;
  name: string;
  city?: string;
  min_level?: number | null;
  max_level?: number;
  difficulty?: string;
  requires_quest?: boolean | null;
  quest_id?: number | null;
  quest_name?: string | null;
  quest_slug?: string | null;
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
  hitpoints: number | null;
  experience: number | null;
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
  hitpoints: number | null;
  experience: number | null;
  armor: number | null;
  speed: number | null;
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
  min_level?: number | null;
  max_level?: number;
  recommended_level?: number;
  recommended_vocations?: string[];
  vocation_recommendations?: Record<string, { level: number | null; skill: number | null; defense: number | null }> | null;
  recommended_party_size?: string;
  exp_rating?: string;
  profit_rating?: string;
  danger_rating?: string;
  knights_recommended?: boolean | null;
  paladins_recommended?: boolean | null;
  sorcerers_recommended?: boolean | null;
  druids_recommended?: boolean | null;
  monks_recommended?: boolean | null;  // Winter Update 2025
  size?: string;
  difficulty?: string;
  avg_exp_hour?: number;
  avg_profit_hour?: number;
  requires_quest?: boolean | null;
  quest_id?: number | null;
  quest_name?: string;
  quest_slug?: string;
  requires_premium?: boolean | null;
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
  external_id?: string | null;
  knowledge_entity_id?: string | null;
  supplied_fields?: string[] | null;
  missing_fields?: string[] | null;
  data_sources?: string[] | null;
  data_version?: number | null;
  access?: {
    status: 'unknown' | 'documented' | 'restricted';
    minimum_level?: number | null;
    maximum_level?: number | null;
    premium_required?: boolean | null;
    quest_required?: boolean | null;
    quests: Array<{ id?: number | null; name: string; slug?: string | null }>;
    notes?: string | null;
    source_provider?: string | null;
    source_url?: string | null;
  };
  creatures?: CreatureSimple[];
  creature_spawns?: Array<{
    id: number;
    creature_id: number;
    quantity?: string;
    notes?: string;
    creature?: CreatureSimple;
  }>;
  last_synced_at?: string;
}

export interface ItemDropCreature {
  creature_id?: number | null;
  creature_name: string;
  creature_slug?: string;
  chance?: number | null;
  rarity?: string | null;
  min_amount?: number | null;
  max_amount?: number | null;
  is_boss: boolean;
  hunt_zones: HuntZoneSimple[];
  relationship_id?: string | null;
  knowledge_entity_id?: string | null;
  resolution_status?: 'resolved' | 'unresolved' | 'ambiguous' | null;
  source_provider?: string | null;
}

export interface ItemRelatedEntity {
  kind: 'npc' | 'quest' | 'location';
  name: string;
  slug: string;
}

export interface ItemSearchResult {
  id?: number | null;
  image_item_id?: number | null;
  item_name: string;
  normalized_name: string;
  slug?: string | null;
  item_image_url?: string | null;
  source_url?: string | null;
  knowledge_entity_id?: string | null;
  canonical_id?: string | null;
  external_id?: string | null;
  source_provider?: string | null;
  supplied_fields: string[];
  missing_fields: string[];
  tradeable?: boolean | null;
  stackable?: boolean | null;
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
  slug?: string | null;
  item_image_url?: string | null;
  source_url?: string | null;
  rarity?: string | null;
  drop_chance?: number | null;
  knowledge_entity_id?: string | null;
  canonical_id?: string | null;
  external_id?: string | null;
  source_provider?: string | null;
  supplied_fields: string[];
  missing_fields: string[];
  data_version: number;
  last_synced_at?: string | null;
  game_item_id?: number | null;
  item_class?: string | null;
  item_type?: string | null;
  category?: string | null;
  weight?: number | null;
  value?: number | null;
  level_requirement?: number | null;
  tradeable?: boolean | null;
  stackable?: boolean | null;
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
  related_entities: ItemRelatedEntity[];
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
  premium_required?: boolean | null;
  repeatable?: boolean | null;
  knowledge_entity_id?: string | null;
  canonical_id?: string | null;
  external_id?: string | null;
  source_provider?: string | null;
  supplied_fields: string[];
  missing_fields: string[];
  data_version: number;
  last_synced_at?: string | null;
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
  canonical_id?: string | null;
  external_id?: string | null;
  source_provider?: string | null;
  supplied_fields: string[];
  missing_fields: string[];
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
  premium_required?: boolean | null;
  repeatable?: boolean | null;
  solo_possible?: boolean | null;
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
  id: string; canonical_id: string; external_id?: string; source_provider: string; source_url?: string;
  supplied_fields: string[]; missing_fields: string[]; data_version: number; last_synced_at?: string;
  title: string; sequence: number; description?: string;
  objectives: string[]; required_items: QuestItemValue[]; rewarded_items: QuestItemValue[];
  related_npcs: QuestNamedValue[]; related_creatures: QuestNamedValue[]; locations: QuestNamedValue[];
}
export interface QuestRelationship {
  canonical_id: string; relation_type: string; target_canonical_id?: string; target_entity_type: string; target_name: string;
  resolution_status: 'resolved' | 'unresolved' | 'ambiguous'; target_slug?: string; mission_id?: string;
  source_providers: string[]; last_synced_at?: string;
}

export interface NamedKnowledgeRelationship {
  canonical_id: string;
  target_canonical_id?: string | null;
  relationship_type: string;
  target_name: string;
  target_type: string;
  target_slug?: string;
  resolution_state: 'resolved' | 'unresolved' | 'ambiguous';
  confidence: string;
  source_providers: string[];
  last_synced_at: string;
}

export interface NamedKnowledgeSummary {
  id: number;
  name: string;
  slug: string;
  knowledge_entity_id: string;
  canonical_id: string;
  external_id: string;
  entity_type: 'npc' | 'location' | 'area' | 'town';
  description?: string;
  image_url?: string;
  source_url?: string;
  source_provider: string;
  supplied_fields: string[];
  missing_fields: string[];
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
  id: string; canonical_id: string; knowledge_entity_id: string; external_id: string;
  source_provider?: string; source_url?: string; supplied_fields: string[]; missing_fields: string[];
  data_version: number; last_synced_at?: string; provider_metadata: Record<string, unknown>;
  name: string; x?: number; y?: number; z?: number;
  location?: { canonical_id?: string | null; name?: string | null } | null;
  confidence: string; verification_state: string;
}

export interface SpatialRegionMetadata {
  id: string; canonical_id: string; knowledge_entity_id: string; external_id: string;
  source_provider?: string; source_url?: string; supplied_fields: string[]; missing_fields: string[];
  data_version: number; last_synced_at?: string; provider_metadata: Record<string, unknown>;
  name: string; location?: { canonical_id?: string | null; name?: string | null } | null;
  bounds: { min_x?: number; min_y?: number; max_x?: number; max_y?: number; min_z?: number; max_z?: number };
  confidence: string; verification_state: string;
}

export interface SpatialRouteStep {
  id: string; sequence: number; kind: string; instruction?: string; location_name?: string;
  location?: { canonical_id?: string | null; name?: string | null };
  provider_metadata: Record<string, unknown>;
  x?: number; y?: number; z?: number;
}

export interface SpatialRouteMetadata {
  id: string; canonical_id: string; knowledge_entity_id: string; external_id: string;
  source_provider?: string; source_url?: string; supplied_fields: string[]; missing_fields: string[];
  data_version: number; last_synced_at?: string; provider_metadata: Record<string, unknown>;
  name: string; slug: string; step_count: number;
  start_location?: string; end_location?: string; confidence: string; verification_state: string;
  start: { canonical_id?: string | null; name?: string | null };
  end: { canonical_id?: string | null; name?: string | null };
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
