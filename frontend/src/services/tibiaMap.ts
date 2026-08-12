import api from './api';

export type TibiaMapLayer = 'hunt_zone' | 'creature' | 'boss' | 'quest' | 'location';

export interface TibiaMapResult {
  id: string;
  entity_type: TibiaMapLayer;
  entity_id: number;
  name: string;
  slug?: string | null;
  to: string;
  subtitle?: string | null;
  x?: number | null;
  y?: number | null;
  z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  geometry_status: 'mapped' | 'knowledge_only';
  creature_count?: number;
  related_hunt_zones?: TibiaMapResult[];
}

export interface TibiaMapBootstrap {
  base_map: null | { zone_id: number; image_url: string; bounds?: Record<string, unknown> | null; floor?: number | null; source: string };
  hunt_zones: TibiaMapResult[];
}

export const tibiaMapApi = {
  async bootstrap(signal?: AbortSignal): Promise<TibiaMapBootstrap> {
    return (await api.get('/map/bootstrap', { signal })).data;
  },
  async search(query: string, layers: TibiaMapLayer[], signal?: AbortSignal): Promise<TibiaMapResult[]> {
    const response = await api.get('/map/search', { params: { q: query, layers: layers.join(','), limit: 40 }, signal });
    return response.data.items || [];
  },
};
