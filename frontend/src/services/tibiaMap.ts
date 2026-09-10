import api from './api';

export type TibiaMapLayer = 'hunt_zone' | 'creature' | 'boss' | 'quest' | 'npc' | 'location';
export type TibiaMapSearchType = TibiaMapLayer | 'item';
export type TibiaMapEntityType = TibiaMapSearchType | 'town';
export type TibiaMapSpatialState = 'resolved_point' | 'resolved_area' | 'knowledge_only' | 'unresolved';
export interface SpatialEvidence {
  x: number; y: number; z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  label?: string | null; relationship?: string | null; role?: string | null;
  spatial_state: 'resolved_point' | 'resolved_area'; geometry_source?: string | null;
  source_provider?: string | null; confidence?: string | null;
}
export interface TibiaMapResult {
  id: string; canonical_entity_id?: string | null; entity_type: TibiaMapEntityType;
  entity_id?: number; name: string; slug?: string | null; to?: string;
  navigation_url?: string; subtitle?: string | null; image_url?: string | null;
  x?: number | null; y?: number | null; z?: number | null;
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  geometry_status: 'mapped' | 'knowledge_only'; spatial_state?: TibiaMapSpatialState;
  geometry_source?: string | null; creature_count?: number; preview?: Record<string, unknown>;
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
export interface TibiaMapBootstrap {
  world_map: WorldMapFloor | null; available_floors: number[];
  towns: TibiaMapResult[]; default_results: TibiaMapResult[];
}
export interface TibiaMapLayerResult {
  layer: TibiaMapLayer; floor: number | null; items: TibiaMapResult[];
  total: number; has_more: boolean;
}
export interface TibiaMapViewport {
  minX: number; minY: number; maxX: number; maxY: number; zoom: number; floor: number;
}
export interface TibiaMapViewportResponse {
  floor: number;
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number };
  layers: TibiaMapLayer[]; zoom: number; items: TibiaMapResult[];
  page: { limit: number; has_more: boolean; next_cursor: string | null };
}

const CACHE_TTL_MS = 5 * 60 * 1000;
interface CacheEntry<T> { value: T; expiresAt: number }
const bootstrapCache = new Map<number, CacheEntry<TibiaMapBootstrap>>();
const huntZoneContextCache = new Map<string, CacheEntry<HuntZoneMapContext>>();
const VIEWPORT_CACHE_SIZE = 24;
const viewportCache = new Map<string, CacheEntry<TibiaMapViewportResponse>>();
const SEARCH_TYPES: TibiaMapSearchType[] = ['hunt_zone', 'creature', 'boss', 'item', 'quest', 'npc', 'location'];

function readCache<K, V>(cache: Map<K, CacheEntry<V>>, key: K): V | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return null;
  }
  // Map insertion order provides a small bounded LRU without another dependency.
  cache.delete(key);
  cache.set(key, entry);
  return entry.value;
}

function viewportRequest(viewport: TibiaMapViewport, layers: TibiaMapLayer[]) {
  const zoomBucket = Math.floor(viewport.zoom);
  const bucketSize = zoomBucket < -2 ? 256 : zoomBucket < 0 ? 128 : zoomBucket < 2 ? 64 : 32;
  const minX = Math.floor(viewport.minX / bucketSize) * bucketSize;
  const minY = Math.floor(viewport.minY / bucketSize) * bucketSize;
  const maxX = Math.ceil(viewport.maxX / bucketSize) * bucketSize;
  const maxY = Math.ceil(viewport.maxY / bucketSize) * bucketSize;
  const active = [...layers].sort();
  return {
    key: [viewport.floor, minX, minY, maxX, maxY, active.join(','), zoomBucket].join(':'),
    params: { min_x: minX, min_y: minY, max_x: maxX, max_y: maxY, floor: viewport.floor, layers: active.join(','), zoom: viewport.zoom, limit: 200 },
  };
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
  async search(query: string, signal?: AbortSignal): Promise<TibiaMapResult[]> {
    const response = await api.get('/map/search', { params: { q: query, layers: SEARCH_TYPES.join(','), limit: 30 }, signal });
    return response.data.items || [];
  },
  async viewport(viewport: TibiaMapViewport, layers: TibiaMapLayer[], signal?: AbortSignal): Promise<TibiaMapViewportResponse> {
    const request = viewportRequest(viewport, layers);
    const cached = readCache(viewportCache, request.key);
    if (cached) return cached;
    const value = (await api.get('/map/viewport', { params: request.params, signal })).data as TibiaMapViewportResponse;
    viewportCache.set(request.key, { value, expiresAt: Date.now() + CACHE_TTL_MS });
    while (viewportCache.size > VIEWPORT_CACHE_SIZE) {
      const oldest = viewportCache.keys().next().value as string | undefined;
      if (oldest == null) break;
      viewportCache.delete(oldest);
    }
    return value;
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

export function buildMapEntityUrl(value: {
  canonicalEntityId?: string | null;
  entityType: TibiaMapSearchType;
  name: string;
  slug?: string | null;
  floor?: number | null;
  location?: string | null;
}): string {
  const params = new URLSearchParams({ q: value.name, entityType: value.entityType });
  if (value.canonicalEntityId) params.set('entity', value.canonicalEntityId);
  if (value.slug) params.set('slug', value.slug);
  if (value.floor != null) params.set('floor', String(value.floor));
  if (value.location) params.set('location', value.location);
  return `/map?${params.toString()}`;
}
