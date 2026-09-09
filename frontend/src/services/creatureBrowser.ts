import api from './api';

export interface CreatureBrowseLoot {
  id: number;
  item_name: string;
  percentage?: number | null;
  rarity?: string | null;
  item_value?: number | null;
  media: { status: 'available' | 'unavailable'; url: string | null };
}

export interface CreatureBrowseLocation {
  id?: number | null;
  name: string;
  slug?: string | null;
  city?: string | null;
  region?: string | null;
  map_image_url?: string | null;
}

export interface CreatureBrowseItem {
  id: number;
  slug?: string | null;
  name: string;
  hitpoints?: number | null;
  experience?: number | null;
  is_boss: boolean;
  difficulty?: string | null;
  classification?: string | null;
  bestiary_level?: string | null;
  bestiary_class?: string | null;
  creature_class?: string | null;
  primary_type?: string | null;
  location_preview?: CreatureBrowseLocation | null;
  loot_preview: CreatureBrowseLoot[];
}

export interface CreatureCombatModifier {
  name: string;
  kind: 'weakness' | 'resistance';
  damage_percent?: number | null;
  delta_percent?: number | null;
}

export interface CreaturePreview {
  id: number;
  slug?: string | null;
  name: string;
  difficulty?: string | null;
  classification?: string | null;
  bestiary_level?: string | null;
  bestiary_class?: string | null;
  creature_class?: string | null;
  primary_type?: string | null;
  description?: string | null;
  behavior?: string | null;
  hitpoints?: number | null;
  experience?: number | null;
  charm_points?: number | null;
  image_url: string;
  loot: CreatureBrowseLoot[];
  locations: CreatureBrowseLocation[];
  combat_modifiers: CreatureCombatModifier[];
}

const itemCache = new Map<number, CreatureBrowseItem>();
const previewCache = new Map<number, CreaturePreview>();

export const creatureBrowserApi = {
  getItems: async (ids: number[], signal?: AbortSignal): Promise<CreatureBrowseItem[]> => {
    const unique = [...new Set(ids.filter((id) => Number.isFinite(id) && id > 0))];
    const missing = unique.filter((id) => !itemCache.has(id));
    if (missing.length > 0) {
      const { data } = await api.get<CreatureBrowseItem[]>('/creatures/browser-items', {
        params: { ids: missing.slice(0, 60).join(',') },
        signal,
      });
      for (const item of data) itemCache.set(item.id, item);
    }
    return unique.map((id) => itemCache.get(id)).filter((item): item is CreatureBrowseItem => Boolean(item));
  },

  getPreview: async (id: number, signal?: AbortSignal): Promise<CreaturePreview> => {
    const cached = previewCache.get(id);
    if (cached) return cached;
    const { data } = await api.get<CreaturePreview>(`/creatures/${id}/preview`, { signal });
    previewCache.set(id, data);
    return data;
  },
};
