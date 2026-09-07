import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const page = read('src/pages/TibiaMapPage.tsx');
const viewer = read('src/components/map/TibiaMapViewer.tsx');
const api = read('src/services/tibiaMap.ts');
const backend = read('../backend/app/services/map_viewport_service.py');

assert.match(api, /api\.get\('\/map\/viewport'/, 'general map browsing must use the bounded viewport endpoint');
for (const parameter of ['min_x', 'min_y', 'max_x', 'max_y', 'floor', 'layers', 'zoom']) {
  assert.match(api, new RegExp(`\\b${parameter}\\b`), `viewport request must include ${parameter}`);
}
assert.match(api, /signal \}\)/, 'viewport request must pass an AbortSignal');
assert.match(page, /\}, 275\)/, 'viewport requests must debounce settled pan/zoom events');
assert.match(page, /viewportRequestSequence/, 'late viewport responses must be ignored');
assert.match(viewer, /map\.on\('moveend zoomend', report\)/, 'viewer must report only settled pan/zoom state');
assert.match(viewer, /onViewportChange\?/, 'viewer must expose the viewport contract');
assert.match(api, /VIEWPORT_CACHE_SIZE = 24/, 'viewport cache must have a small hard bound');
assert.match(api, /while \(viewportCache\.size > VIEWPORT_CACHE_SIZE\)/, 'viewport cache must evict old entries');
assert.doesNotMatch(api, /\/map\/layers\//, 'general map browsing must not use whole-layer endpoints');
assert.doesNotMatch(api, /limit:\s*250/, 'whole-layer 250-row requests must not remain');
assert.match(page, /new Set\(layers\)/, 'all six supported layers must be enabled initially');
for (const layer of ['creature', 'boss', 'quest', 'npc', 'hunt_zone', 'location']) {
  assert.match(page, new RegExp(`\\b${layer}\\b`), `general map controls must retain ${layer}`);
}
assert.match(page, /markersForMapMode\(isolatedMarkerMode, layerMarkers, entityMarkers\)/, 'selected/search mode must remain isolated');
assert.match(page, /clearSearch/, 'clearing search must retain the viewport-mode transition');
assert.doesNotMatch(`${page}\n${viewer}\n${api}`, /https?:\/\//, 'frontend map browsing must not introduce an external media host');
assert.doesNotMatch(page, /Thais|\b32\d{3}\b/, 'frontend must not add a fabricated Thais anchor');
assert.match(page, /lg:flex-row/, 'responsive map controls must remain intact');
assert.match(backend, /WorldMapMarker\.x >= min_x/, 'marker candidates must be bbox-filtered in SQL');
assert.match(backend, /SpatialMapRegion\.min_x < max_x/, 'regions must use intersection filtering in SQL');
assert.doesNotMatch(backend, /requests\.|httpx\.|urllib/, 'viewport projection must not call a provider/network client');

console.log('Phase 4.5 checks passed: bounded viewport loading, settled-event debounce, bounded LRU, all layers, isolation, local-only media, and no fabricated anchor.');
