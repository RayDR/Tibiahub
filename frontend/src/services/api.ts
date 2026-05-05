import axios from 'axios';
import type { Creature, CreatureSimple, HuntZone, HuntRecommendation, ItemDetail, ItemSearchResult, QuestDetail, QuestSearchResult, Vocation } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
export const REQUEST_TIMEOUT_MS = 10000;
export const ADMIN_ACTION_TIMEOUT_MS = 25000;

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

  getById: async (id: number): Promise<HuntZone> => {
    const response = await api.get(`/hunt-zones/${id}`);
    return response.data;
  },

  getMapImageUrl: (id: number): string => `${API_BASE_URL}/hunt-zones/${id}/map-image`,

  getRecommendations: async (
    vocation: Vocation,
    level: number,
    limit: number = 10
  ): Promise<HuntRecommendation[]> => {
    // UPDATED: Use new /recommendations/solo endpoint
    const response = await api.get('/recommendations/solo', {
      params: { vocation, level, limit, goal: 'exp' },
    });

    // Map response to HuntRecommendation type
    // The backend returns { recommendations: [ { zone: {...}, score: ..., reasons: ... } ] }
    if (response.data && response.data.recommendations) {
      return response.data.recommendations.map((rec: any) => ({
        zone: {
          id: rec.zone_id,
          name: rec.zone_name,
          min_level: rec.min_level,
          difficulty: rec.difficulty,
          // Add default fields if missing from simplified response
          city: '',
          max_level: rec.max_level
        },
        score: rec.score,
        reasons: rec.reasons,
        creatures: []
      }));
    }
    return [];
  },

  getPartyRecommendations: async (
    party_composition: Array<{ vocation: string; level: number }>,
    goal: 'exp' | 'profit' | 'balanced' = 'exp'
  ): Promise<any> => {
    // UPDATED: Use new /recommendations/party endpoint
    const response = await api.post('/recommendations/party', party_composition, {
      params: { goal },
    });
    return response.data;
  },
};

// Items API
export const itemsApi = {
  search: async (search: string, limit: number = 50, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/', { params: { search, limit }, signal });
    return response.data;
  },

  list: async (params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/', { params, signal });
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
};

export const questsApi = {
  list: async (params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/', { params, signal });
    return response.data;
  },

  search: async (search: string, limit: number = 50, signal?: AbortSignal): Promise<QuestSearchResult[]> => {
    const response = await api.get('/quests/', { params: { search, limit }, signal });
    return response.data;
  },

  getById: async (id: number, signal?: AbortSignal): Promise<QuestDetail> => {
    const response = await api.get(`/quests/${id}`, { signal });
    return response.data;
  },
};

export const systemApi = {
  getHealth: async (signal?: AbortSignal): Promise<{
    external_sync?: {
      latest_data_version?: string | null;
      latest_success_at?: string | null;
    };
  }> => {
    const response = await api.get('/health', { signal });
    return response.data;
  },
};

export default api;
