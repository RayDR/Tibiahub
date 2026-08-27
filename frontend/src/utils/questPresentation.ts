import type { QuestDetail, QuestSearchResult } from '../types';

const DETAIL_FIELDS = new Set([
  'description', 'summary', 'missions', 'required_items', 'rewarded_items',
  'required_quests', 'requirements', 'locations', 'starting_npcs', 'related_npcs',
  'access_unlocks', 'relationships', 'related_creatures',
]);

const meaningfulText = (value?: string, name?: string) => {
  const normalized = value?.trim();
  return Boolean(normalized && normalized.toLocaleLowerCase() !== name?.trim().toLocaleLowerCase());
};

export function hasDetailedQuestSummary(quest: QuestSearchResult): boolean {
  return meaningfulText(quest.description, quest.name)
    || Boolean(quest.location?.trim() || quest.npc?.trim())
    || quest.supplied_fields.some((field) => DETAIL_FIELDS.has(field));
}

export function hasDetailedQuestData(quest: QuestDetail): boolean {
  return meaningfulText(quest.summary || quest.description, quest.name)
    || quest.missions.length > 0
    || quest.required_items.length > 0
    || quest.required_quests.length > 0
    || quest.requirements.length > 0
    || quest.rewarded_items.length > 0
    || Boolean(quest.rewards?.length)
    || quest.locations.length > 0
    || quest.starting_npcs.length > 0
    || quest.related_npcs.length > 0
    || quest.access_unlocks.length > 0
    || quest.related_creatures.length > 0
    || quest.relationships.some((relationship) => relationship.resolution_status === 'resolved');
}

export function questDetailCounts(quest?: QuestDetail | null) {
  return {
    missions: quest?.missions.length || 0,
    rewards: quest ? Math.max(quest.rewarded_items.length, quest.rewards?.length || 0) : 0,
    requirements: quest ? Math.max(quest.required_items.length + quest.required_quests.length, quest.requirements.length) : 0,
    locations: quest ? Math.max(quest.locations.length, quest.location?.trim() ? 1 : 0) : 0,
  };
}
