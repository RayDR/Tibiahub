import axios from 'axios';
import type { Creature, CreatureSimple, HuntZone, ItemDetail, ItemSearchResult, LocationKnowledgeDetail, NpcKnowledgeDetail, QuestDetail, QuestSearchResult, SpatialRouteMetadata, Vocation } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
export const REQUEST_TIMEOUT_MS = 10000;
export const LOGIN_TIMEOUT_MS = 20000;
export const ADMIN_ACTION_TIMEOUT_MS = 30000;
export const HEALTH_TIMEOUT_MS = 5000;

export interface CreatureCategoryPreview {
  id: number;
  name: string;
  slug?: string | null;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Creatures API
export const creaturesApi = {
  getAll: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    category?: string;
    is_boss?: boolean;
    difficulty?: string;
    sort_by?: 'name' | 'experience' | 'hitpoints' | 'difficulty';
    sort_order?: 'asc' | 'desc';
  }, signal?: AbortSignal): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/', { params, signal });
    return response.data;
  },

  getHighlights: async (limit: number = 18, signal?: AbortSignal): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/highlights', { params: { limit }, signal });
    return response.data;
  },

  getPopular: async (
    limit: number = 12,
    signal?: AbortSignal,
  ): Promise<CreatureSimple[]> => {
    const response = await api.get(
      '/creatures/popular',
      {
        params: { limit },
        signal,
      },
    );

    return response.data;
  },

  getBosses: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    sort_by?: 'name' | 'experience' | 'hitpoints' | 'difficulty';
    sort_order?: 'asc' | 'desc';
  }, signal?: AbortSignal): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/bosses', { params, signal });
    return response.data;
  },

  getPopularBosses: async (
    limit: number = 12,
    signal?: AbortSignal,
  ): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/bosses/popular', {
      params: { limit },
      signal,
    });
    return response.data;
  },

  getCategoryImages: async (
    signal?: AbortSignal,
  ): Promise<Record<string, string>> => {
    const response = await api.get(
      '/creatures/category-images',
      { signal },
    );
    return response.data || {};
  },

  getCategoryPreviews: async (
    signal?: AbortSignal,
  ): Promise<Record<string, CreatureCategoryPreview[]>> => {
    const response = await api.get(
      '/creatures/category-previews',
      { signal },
    );
    return response.data || {};
  },

  getCategoryCounts: async (
    signal?: AbortSignal,
  ): Promise<Record<string, number>> => {
    const response = await api.get(
      '/creatures/category-counts',
      { signal },
    );
    return response.data || {};
  },

  getById: async (id: number): Promise<Creature> => {
    const response = await api.get(`/creatures/${id}`);
    return response.data;
  },

  getBySlug: async (slug: string): Promise<Creature> => {
    const response = await api.get(`/creatures/${encodeURIComponent(slug)}`);
    return response.data;
  },

  getByName: async (name: string): Promise<Creature> => {
    const response = await api.get(`/creatures/name/${name}`);
    return response.data;
  },
};

// Hunt Zones API
// Hunt Zones API
export const huntZonesApi = {
  getAll: async (filters: { skip?: number; limit?: number; min_level?: number; max_level?: number; city?: string; search?: string } = {}, signal?: AbortSignal): Promise<HuntZone[]> => {
    const response = await api.get('/hunt-zones/', { params: filters, signal });
    return response.data;
  },

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<HuntZone[]> => {
    const response = await api.get('/hunt-zones/highlights', { params: { limit }, signal });
    return response.data;
  },

  getByIdentifier: async (identifier: number | string, signal?: AbortSignal): Promise<HuntZone> => {
    const response = await api.get(`/hunt-zones/${encodeURIComponent(identifier)}`, { signal });
    return response.data;
  },

  getById: async (id: number): Promise<HuntZone> => {
    const response = await api.get(`/hunt-zones/${id}`);
    return response.data;
  },

  getMapImageUrl: (id: number, placeholder: boolean = true): string => `${API_BASE_URL}/hunt-zones/${id}/map-image?placeholder=${placeholder}`,

  getRecommendations: async (
    vocation: Vocation,
    level: number,
    limit: number = 10,
    goal: 'exp' | 'profit' | 'balanced' = 'exp',
    zone?: string,
    skip: number = 0,
  ): Promise<any> => {
    const response = await api.get('/recommendations/solo', {
      params: { vocation, level, limit, goal, zone, skip },
    });
    return response.data;
  },

  getPartyRecommendations: async (
    party_composition: Array<{ vocation: string; level: number }>,
    goal: 'exp' | 'profit' | 'balanced' = 'exp',
    limit: number = 6,
    skip: number = 0,
  ): Promise<any> => {
    // UPDATED: Use new /recommendations/party endpoint
    const response = await api.post('/recommendations/party', party_composition, {
      params: { goal, limit, skip },
    });
    return response.data;
  },
};

// Items API
export const itemsApi = {
  search: async (search: string, limit: number = 50, signal?: AbortSignal, skip: number = 0): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/', { params: { search, limit, skip }, signal });
    return response.data;
  },

  list: async (params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/', { params, signal });
    return response.data;
  },

  getByIdentifier: async (identifier: number | string, signal?: AbortSignal): Promise<ItemDetail> => {
    const response = await api.get(`/items/${encodeURIComponent(identifier)}`, { signal });
    return response.data;
  },

  getById: async (id: number, signal?: AbortSignal): Promise<ItemDetail> => {
    const response = await api.get(`/items/${id}`, { signal });
    return response.data;
  },

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/highlights', { params: { limit }, signal });
    return response.data;
  },

  getPopular: async (limit: number = 12, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/popular', { params: { limit }, signal });
    return response.data;
  },

  getTrending: async (limit: number = 12, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/trending', { params: { limit }, signal });
    return response.data;
  },
};

export const questsApi = {
  list: async (params?: { skip?: number; limit?: number; include_groups?: boolean; category?: string; level?: number; premium?: boolean; repeatable?: boolean }, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/', { params, signal });
    return response.data;
  },

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/highlights', { params: { limit }, signal });
    return response.data;
  },

  getPopular: async (limit: number = 10, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/popular', { params: { limit }, signal });
    return response.data;
  },

  getTrending: async (limit: number = 10, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/trending', { params: { limit }, signal });
    return response.data;
  },

  search: async (search: string, limit: number = 50, signal?: AbortSignal, include_groups: boolean = false, skip: number = 0): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/', { params: { search, limit, include_groups, skip }, signal });
    return response.data;
  },

  getById: async (id: number | string, signal?: AbortSignal): Promise<QuestDetail> => {
    const response = await api.get(`/quests/${id}`, { signal });
    return response.data;
  },
};

export const namedKnowledgeApi = {
  getNpc: async (identifier: string, signal?: AbortSignal): Promise<NpcKnowledgeDetail> => {
    const response = await api.get(`/npcs/${encodeURIComponent(identifier)}`, { signal });
    return response.data;
  },

  getLocation: async (identifier: string, signal?: AbortSignal): Promise<LocationKnowledgeDetail> => {
    const response = await api.get(`/locations/${encodeURIComponent(identifier)}`, { signal });
    return response.data;
  },
};

export const spatialApi = {
  forLocation: async (identifier: string, signal?: AbortSignal) => (
    await api.get(`/spatial/locations/${encodeURIComponent(identifier)}`, { signal })
  ).data,
  forEntity: async (entityId: string, signal?: AbortSignal) => (
    await api.get(`/spatial/entities/${encodeURIComponent(entityId)}`, { signal })
  ).data,
  route: async (identifier: string, signal?: AbortSignal): Promise<SpatialRouteMetadata> => (
    await api.get(`/spatial/routes/${encodeURIComponent(identifier)}`, { signal })
  ).data,
  nearby: async (x: number, y: number, z: number, signal?: AbortSignal): Promise<{ items: Array<{ source_entity_id: string; canonical_name: string; entity_type: string; slug: string; distance: number }> }> => (
    await api.get('/spatial/nearby', { params: { x, y, z, distance: 50, limit: 12 }, signal })
  ).data,
};

export const adminCreaturesApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    include_hidden?: boolean;
  }, signal?: AbortSignal): Promise<{ items: Creature[]; total: number; skip: number; limit: number }> => {
    const response = await api.get('/admin/creatures', { params, signal });
    return response.data;
  },

  patch: async (
    creatureId: number,
    payload: {
      name?: string;
      classification?: string | null;
      difficulty?: string | null;
      is_hidden?: boolean;
      image_alias?: string | null;
      image_url_override?: string | null;
      image_source_name?: string | null;
      image_locked?: boolean;
      clear_local_cache?: boolean;
    }
  ): Promise<any> => {
    const response = await api.patch(`/admin/creatures/${creatureId}/image`, payload, {
      timeout: ADMIN_ACTION_TIMEOUT_MS,
    });
    return response.data;
  },
};

export const adminOverviewApi = {
  getStats: async (signal?: AbortSignal) => {
    const response = await api.get('/admin/overview/stats', { signal });
    return response.data as {
      creatures: { total: number; visible: number; hidden: number };
      hunt_zones: { total: number };
      quests: { total: number };
      users: { total: number; active: number; inactive: number; admin: number };
    };
  },
};

export const systemApi = {
  getHealth: async (signal?: AbortSignal): Promise<{
    external_sync?: {
      latest_data_version?: string | null;
      latest_success_at?: string | null;
    };
  }> => {
    const response = await api.get('/health', { signal, timeout: HEALTH_TIMEOUT_MS });
    return response.data;
  },
};

export default api;
