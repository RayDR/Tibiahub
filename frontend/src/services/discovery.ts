import api from './api';

export interface DiscoveryCard { id: string | number; name: string; slug?: string; image_url?: string; experience?: number; hitpoints?: number; city?: string; recommended_level?: number; summary?: string; entity_type?: string; updated_at?: string; search_count?: number }
export interface CyclopediaDiscovery {
  featured_creatures: DiscoveryCard[];
  popular_hunts: DiscoveryCard[];
  recent_quests: DiscoveryCard[];
  latest_knowledge: DiscoveryCard[];
  trending: DiscoveryCard[];
  boosted_creature: DiscoveryCard | null;
  boosted_boss: DiscoveryCard | null;
  boosted_state: 'available' | 'awaiting_official_sync';
}

export const discoveryApi = {
  load: async (): Promise<CyclopediaDiscovery> => (await api.get('/catalog/discovery')).data,
};
