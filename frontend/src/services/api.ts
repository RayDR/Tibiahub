import axios from 'axios';
import type { Creature, CreatureSimple, HuntZone, HuntRecommendation, ItemSearchResult, Vocation } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
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
    difficulty?: string;
    sort_by?: 'name' | 'experience' | 'hitpoints' | 'difficulty';
    sort_order?: 'asc' | 'desc';
  }): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/', { params });
    return response.data;
  },

  getHighlights: async (limit: number = 18): Promise<CreatureSimple[]> => {
    const response = await api.get('/creatures/highlights', { params: { limit } });
    return response.data;
  },

  getById: async (id: number): Promise<Creature> => {
    const response = await api.get(`/creatures/${id}`);
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
  getAll: async (filters: { skip?: number; limit?: number; min_level?: number; max_level?: number; city?: string; search?: string } = {}): Promise<HuntZone[]> => {
    const response = await api.get('/hunt-zones/', { params: filters });
    return response.data;
  },

  getHighlights: async (limit: number = 12): Promise<HuntZone[]> => {
    const response = await api.get('/hunt-zones/highlights', { params: { limit } });
    return response.data;
  },

  getById: async (id: number): Promise<HuntZone> => {
    const response = await api.get(`/hunt-zones/${id}`);
    return response.data;
  },

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
  search: async (search: string, limit: number = 50): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/', { params: { search, limit } });
    return response.data;
  },

  getHighlights: async (limit: number = 12): Promise<ItemSearchResult[]> => {
    const response = await api.get('/items/highlights', { params: { limit } });
    return response.data;
  },
};

export default api;
