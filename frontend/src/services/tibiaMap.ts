import api from './api';

export type TibiaMapLayer = 'hunt_zone' | 'creature' | 'boss' | 'quest' | 'location';
export type TibiaMapEntityType = TibiaMapLayer | 'town';
export interface TibiaMapResult {
  id: string; entity_type: TibiaMapEntityType; entity_id?: number; name: string;
  slug?: string | null; to?: string; subtitle?: string | null; image_url?: string;
  x?: number | null; y?: number | null; z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  geometry_status: 'mapped' | 'knowledge_only'; geometry_source?: string | null; creature_count?: number;
}
export interface WorldMapFloor {
  floor: number; image_url: string; pathfinding_url?: string | null; width: number; height: number;
  bounds: Record<string, unknown>; provider: string; upstream_url: string; upstream_commit: string;
  map_sha256: string; pathfinding_sha256?: string; license: string; attribution: string;
}
export interface HuntZoneMapContext {
  hunt_zone: TibiaMapResult;
  creatures: Array<{ id: number; name: string; slug?: string; image_url: string; hitpoints: number | null; experience: number | null; geometry_status: string }>;
  markers: Array<{ x: number; y: number; z?: number; name: string; image_url?: string }>;
  routes: Array<{ id: string; name: string; points: Array<{ x: number; y: number; z?: number }> }>;
}
export interface TibiaMapBootstrap { world_map: WorldMapFloor | null; available_floors: number[]; towns: TibiaMapResult[] }

export const tibiaMapApi = {
  async bootstrap(floor: number, signal?: AbortSignal): Promise<TibiaMapBootstrap> {
    return (await api.get('/map/bootstrap', { params: { floor }, signal })).data;
  },
  async search(query: string, layers: TibiaMapLayer[], signal?: AbortSignal): Promise<TibiaMapResult[]> {
    const response = await api.get('/map/search', { params: { q: query, layers: layers.join(','), limit: 30 }, signal });
    return response.data.items || [];
  },
  async huntZoneContext(identifier: number | string, signal?: AbortSignal): Promise<HuntZoneMapContext> {
    return (await api.get(`/map/hunt-zones/${encodeURIComponent(identifier)}/context`, { signal })).data;
  },
};
