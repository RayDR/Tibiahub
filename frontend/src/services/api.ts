import axios, { type AxiosRequestConfig } from 'axios';
import type { Creature, CreatureSimple, HuntZone, ItemDetail, ItemSearchResult, LocationKnowledgeDetail, NpcKnowledgeDetail, QuestDetail, QuestSearchResult, SpatialRouteMetadata, Vocation } from '../types';
import { cachedKnowledgeRead, knowledgeCacheKey } from './knowledgeRequestCache';

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

async function cachedGet<T>(
  path: string,
  config: AxiosRequestConfig = {},
): Promise<T> {
  const key = knowledgeCacheKey(
    path,
    config.params as Record<string, unknown> | undefined,
  );
  return cachedKnowledgeRead(key, async () => {
    const response = await api.get<T>(path, config);
    return response.data;
  });
}

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
  }, signal?: AbortSignal): Promise<CreatureSimple[]> => (
    cachedGet<CreatureSimple[]>('/creatures/', { params, signal })
  ),

  getHighlights: async (limit: number = 18, signal?: AbortSignal): Promise<CreatureSimple[]> => (
    cachedGet<CreatureSimple[]>('/creatures/highlights', { params: { limit }, signal })
  ),

  getPopular: async (
    limit: number = 12,
    signal?: AbortSignal,
  ): Promise<CreatureSimple[]> => (
    cachedGet<CreatureSimple[]>('/creatures/popular', { params: { limit }, signal })
  ),

  getBosses: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    sort_by?: 'name' | 'experience' | 'hitpoints' | 'difficulty';
    sort_order?: 'asc' | 'desc';
  }, signal?: AbortSignal): Promise<CreatureSimple[]> => (
    cachedGet<CreatureSimple[]>('/creatures/bosses', { params, signal })
  ),

  getPopularBosses: async (
    limit: number = 12,
    signal?: AbortSignal,
  ): Promise<CreatureSimple[]> => (
    cachedGet<CreatureSimple[]>('/creatures/bosses/popular', { params: { limit }, signal })
  ),

  getCategoryImages: async (
    signal?: AbortSignal,
  ): Promise<Record<string, string>> => (
    cachedGet<Record<string, string>>('/creatures/category-images', { signal })
  ),

  getCategoryPreviews: async (
    signal?: AbortSignal,
  ): Promise<Record<string, CreatureCategoryPreview[]>> => (
    cachedGet<Record<string, CreatureCategoryPreview[]>>('/creatures/category-previews', { signal })
  ),

  getCategoryCounts: async (
    signal?: AbortSignal,
  ): Promise<Record<string, number>> => (
    cachedGet<Record<string, number>>('/creatures/category-counts', { signal })
  ),

  getById: async (id: number): Promise<Creature> => (
    cachedGet<Creature>(`/creatures/${id}`)
  ),

  getBySlug: async (slug: string): Promise<Creature> => (
    cachedGet<Creature>(`/creatures/${encodeURIComponent(slug)}`)
  ),

  getByName: async (name: string): Promise<Creature> => (
    cachedGet<Creature>(`/creatures/name/${name}`)
  ),
};

export const huntZonesApi = {
  getAll: async (filters: { skip?: number; limit?: number; min_level?: number; max_level?: number; city?: string; search?: string } = {}, signal?: AbortSignal): Promise<HuntZone[]> => (
    cachedGet<HuntZone[]>('/hunt-zones/', { params: filters, signal })
  ),

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<HuntZone[]> => (
    cachedGet<HuntZone[]>('/hunt-zones/highlights', { params: { limit }, signal })
  ),

  getByIdentifier: async (identifier: number | string, signal?: AbortSignal): Promise<HuntZone> => (
    cachedGet<HuntZone>(`/hunt-zones/${encodeURIComponent(identifier)}`, { signal })
  ),

  getById: async (id: number): Promise<HuntZone> => (
    cachedGet<HuntZone>(`/hunt-zones/${id}`)
  ),

  getMapImageUrl: (id: number, placeholder: boolean = true): string => `${API_BASE_URL}/hunt-zones/${id}/map-image?placeholder=${placeholder}`,

  getRecommendations: async (
    vocation: Vocation,
    level: number,
    limit: number = 10,
    goal: 'exp' | 'profit' | 'balanced' = 'exp',
    zone?: string,
    skip: number = 0,
    signal?: AbortSignal,
  ): Promise<any> => {
    const response = await api.get('/recommendations/solo', {
      params: { vocation, level, limit, goal, zone, skip }, signal,
    });
    return response.data;
  },

  getPartyRecommendations: async (
    party_composition: Array<{ vocation: string; level: number }>,
    goal: 'exp' | 'profit' | 'balanced' = 'exp',
    limit: number = 6,
    skip: number = 0,
    signal?: AbortSignal,
  ): Promise<any> => {
    const response = await api.post('/recommendations/party', party_composition, {
      params: { goal, limit, skip }, signal,
    });
    return response.data;
  },
};

export const itemsApi = {
  search: async (search: string, limit: number = 50, signal?: AbortSignal, skip: number = 0): Promise<ItemSearchResult[]> => (
    cachedGet<ItemSearchResult[]>('/items/', { params: { search, limit, skip }, signal })
  ),

  list: async (params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<ItemSearchResult[]> => (
    cachedGet<ItemSearchResult[]>('/items/', { params, signal })
  ),

  getByIdentifier: async (identifier: number | string, signal?: AbortSignal): Promise<ItemDetail> => (
    cachedGet<ItemDetail>(`/items/${encodeURIComponent(identifier)}`, { signal })
  ),

  getById: async (id: number, signal?: AbortSignal): Promise<ItemDetail> => (
    cachedGet<ItemDetail>(`/items/${id}`, { signal })
  ),

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<ItemSearchResult[]> => (
    cachedGet<ItemSearchResult[]>('/items/highlights', { params: { limit }, signal })
  ),

  getPopular: async (limit: number = 12, signal?: AbortSignal): Promise<ItemSearchResult[]> => (
    cachedGet<ItemSearchResult[]>('/items/popular', { params: { limit }, signal })
  ),

  // Compatibility shim for the legacy second Loot rail. Keep the callable
  // shape until CreaturesPage is split up, but do not issue a redundant GET.
  getTrending: async (
    _limit: number = 12,
    _signal?: AbortSignal,
  ): Promise<ItemSearchResult[]> => [],
};

export const questsApi = {
  list: async (params?: { skip?: number; limit?: number; include_groups?: boolean; category?: string; level?: number; premium?: boolean; repeatable?: boolean }, signal?: AbortSignal): Promise<QuestSearchResult[]> => (
    cachedGet<QuestSearchResult[]>('/quests/', { params, signal })
  ),

  getHighlights: async (limit: number = 12, signal?: AbortSignal): Promise<QuestSearchResult[]> => (
    cachedGet<QuestSearchResult[]>('/quests/highlights', { params: { limit }, signal })
  ),

  getPopular: async (limit: number = 10, signal?: AbortSignal): Promise<QuestSearchResult[]> => (
    cachedGet<QuestSearchResult[]>('/quests/popular', { params: { limit }, signal })
  ),

  getTrending: async (limit: number = 10, signal?: AbortSignal): Promise<QuestSearchResult[]> => (
    cachedGet<QuestSearchResult[]>('/quests/trending', { params: { limit }, signal })
  ),

  search: async (search: string, limit: number = 50, signal?: AbortSignal, include_groups: boolean = false, skip: number = 0): Promise<QuestSearchResult[]> => (
    cachedGet<QuestSearchResult[]>('/quests/', { params: { search, limit, include_groups, skip }, signal })
  ),

  getById: async (id: number | string, signal?: AbortSignal): Promise<QuestDetail> => (
    cachedGet<QuestDetail>(`/quests/${id}`, { signal })
  ),
};

export const namedKnowledgeApi = {
  getNpc: async (identifier: string, signal?: AbortSignal): Promise<NpcKnowledgeDetail> => (
    cachedGet<NpcKnowledgeDetail>(`/npcs/${encodeURIComponent(identifier)}`, { signal })
  ),

  getLocation: async (identifier: string, signal?: AbortSignal): Promise<LocationKnowledgeDetail> => (
    cachedGet<LocationKnowledgeDetail>(`/locations/${encodeURIComponent(identifier)}`, { signal })
  ),
};

export const spatialApi = {
  forLocation: async (identifier: string, signal?: AbortSignal): Promise<any> => (
    cachedGet<any>(`/spatial/locations/${encodeURIComponent(identifier)}`, { signal })
  ),
  forEntity: async (entityId: string, signal?: AbortSignal): Promise<any> => (
    cachedGet<any>(`/spatial/entities/${encodeURIComponent(entityId)}`, { signal })
  ),
  route: async (identifier: string, signal?: AbortSignal): Promise<SpatialRouteMetadata> => (
    cachedGet<SpatialRouteMetadata>(`/spatial/routes/${encodeURIComponent(identifier)}`, { signal })
  ),
  nearby: async (x: number, y: number, z: number, signal?: AbortSignal): Promise<{ items: Array<{ source_entity_id: string; canonical_name: string; entity_type: string; slug: string; distance: number }> }> => (
    cachedGet<{ items: Array<{ source_entity_id: string; canonical_name: string; entity_type: string; slug: string; distance: number }> }>('/spatial/nearby', { params: { x, y, z, distance: 50, limit: 12 }, signal })
  ),
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
