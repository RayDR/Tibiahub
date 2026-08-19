import api from './api';

export type TibiaMapLayer = 'hunt_zone' | 'creature' | 'boss' | 'item' | 'quest' | 'npc' | 'location';
export type TibiaMapEntityType = TibiaMapLayer | 'town';
export interface SpatialEvidence {
  x: number; y: number; z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  label?: string | null; relationship?: string | null; geometry_source?: string | null;
}
export interface TibiaMapResult {
  id: string; entity_type: TibiaMapEntityType; entity_id?: number; name: string;
  slug?: string | null; to?: string; subtitle?: string | null; image_url?: string;
  x?: number | null; y?: number | null; z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  geometry_status: 'mapped' | 'knowledge_only'; geometry_source?: string | null; creature_count?: number;
  spatial_evidence?: SpatialEvidence[]; location_labels?: string[];
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

const CACHE_TTL_MS = 5 * 60 * 1000;
interface CacheEntry<T> { value: T; expiresAt: number }
const bootstrapCache = new Map<number, CacheEntry<TibiaMapBootstrap>>();
const huntZoneContextCache = new Map<string, CacheEntry<HuntZoneMapContext>>();

function readCache<K, V>(cache: Map<K, CacheEntry<V>>, key: K): V | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return null;
  }
  return entry.value;
}

function cacheHuntZoneContext(identifier: number | string, value: HuntZoneMapContext) {
  const entry = { value, expiresAt: Date.now() + CACHE_TTL_MS };
  huntZoneContextCache.set(String(identifier), entry);
  if (value.hunt_zone.entity_id != null) huntZoneContextCache.set(String(value.hunt_zone.entity_id), entry);
  if (value.hunt_zone.slug) huntZoneContextCache.set(value.hunt_zone.slug, entry);
  return value;
}

export const tibiaMapApi = {
  async bootstrap(floor: number, signal?: AbortSignal): Promise<TibiaMapBootstrap> {
    const cached = readCache(bootstrapCache, floor);
    if (cached) return cached;
    const value = (await api.get('/map/bootstrap', { params: { floor }, signal })).data as TibiaMapBootstrap;
    bootstrapCache.set(floor, { value, expiresAt: Date.now() + CACHE_TTL_MS });
    return value;
  },
  async search(query: string, layers: TibiaMapLayer[], signal?: AbortSignal): Promise<TibiaMapResult[]> {
    const response = await api.get('/map/search', { params: { q: query, layers: layers.join(','), limit: 30 }, signal });
    return response.data.items || [];
  },
  async huntZoneContext(identifier: number | string, signal?: AbortSignal): Promise<HuntZoneMapContext> {
    const cached = readCache(huntZoneContextCache, String(identifier));
    if (cached) return cached;
    const value = (await api.get(`/map/hunt-zones/${encodeURIComponent(identifier)}/context`, { signal })).data as HuntZoneMapContext;
    return cacheHuntZoneContext(identifier, value);
  },
  peekHuntZoneContext(identifier: number | string): HuntZoneMapContext | null {
    return readCache(huntZoneContextCache, String(identifier));
  },
  primeHuntZoneContext(identifier: number | string, value: HuntZoneMapContext): void {
    cacheHuntZoneContext(identifier, value);
  },
};
