import fs from 'node:fs';

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const expect = (condition, message) => { if (!condition) throw new Error(message); };

const floor = read('src/utils/tibiaFloors.ts');
const map = read('src/pages/TibiaMapPage.tsx');
const mapViewer = read('src/components/map/TibiaMapViewer.tsx');
const mapService = read('src/services/tibiaMap.ts');
const card = read('src/components/HuntZoneCard.tsx');
const cyclopedia = read('src/pages/CreaturesPage.tsx');
const detail = read('src/pages/HuntZoneDetailPage.tsx');
const metadata = read('src/components/MapMetadataPanel.tsx');
const planner = read('src/pages/HuntRecommendationsPage.tsx');

expect(floor.includes('7 - internalFloor'), 'Ground-floor display must remain a presentation-only z=7 -> floor 0 conversion.');
for (const layer of ["'hunt_zone'", "'creature'", "'boss'", "'item'", "'quest'", "'npc'", "'location'"]) {
  expect(mapService.includes(layer), `Universal map layer missing: ${layer}`);
}
expect(map.includes('locationNotMapped'), 'Map selections need an explicit unmapped state.');
expect(map.includes('100dvh-var(--app-nav-clearance)-var(--app-mobile-nav-clearance)'), 'Map workspace must fill the viewport below primary navigation.');
expect(map.includes('overflow-x-auto') && map.includes('map.layers.${layer}'), 'Map category chips must remain horizontally scrollable and use universal local layers.');
expect(map.includes("entity_type === 'town'") && map.includes('bootstrap?.towns'), 'Town results must come from authoritative map bootstrap data.');
expect(map.includes('townMatches') && map.includes('combined = [...townMatches, ...data]'), 'Known authoritative towns must participate in universal map search.');
expect(map.includes('RECENT_MAP_TARGETS_KEY') && map.includes('entityType: row.entity_type') && !map.includes('x: row.x, y: row.y, z: row.z, name: row.name'), 'Recent map navigation must not persist a second coordinate store.');
expect(map.includes('controlFooter={floorControl}') && mapViewer.includes('{controlFooter}</Controls>'), 'Floor selection must share the right-side map control stack.');
expect(mapViewer.includes('scrollWheelZoom') && mapViewer.includes('touchZoom="center"') && mapViewer.includes('doubleClickZoom'), 'Map must support wheel, trackpad, and touch zoom alongside buttons.');
expect(mapViewer.includes('InitialViewport') && mapViewer.includes('getBoundsZoom(bounds) + 0.5'), 'Initial world framing must use a readable fitted view while retaining reset-to-world.');
expect(mapViewer.includes('relative isolate z-base') && map.includes('z-map-overlay'), 'Leaflet panes and application map overlays must use bounded stacking contexts.');
expect(card.includes('LocalizedMapPreview'), 'Hunt Zone cards must use the localized canonical floor preview.');
expect(cyclopedia.includes('<HuntZoneCard'), 'Cyclopedia Hunt Zones must reuse the shared aligned card.');
expect(!cyclopedia.includes('getMapImageUrl(zone.id'), 'Cyclopedia cards must not reuse broad provider map fragments.');
expect(metadata.includes('Promise.allSettled') && metadata.includes('Nearby is optional'), 'Optional nearby failures must not erase authoritative spatial geometry.');
expect(planner.includes('loading || loadingMore || requestRef.current'), 'Planner infinite scroll must not replace ownership of an active recommendation request.');
expect(mapService.includes('CACHE_TTL_MS') && mapService.includes('expiresAt'), 'Spatial context caches must be bounded rather than session-permanent.');
expect(detail.includes("activity_type: 'view_zone'"), 'Hunt Zone Detail must record visits for the shared personal-history strip.');

console.log('Map/spatial guards passed.');
