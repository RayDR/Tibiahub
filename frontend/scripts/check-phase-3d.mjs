import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8');
const fail = (message) => {
  console.error(`Phase 3D check failed: ${message}`);
  process.exitCode = 1;
};
const requireText = (source, value, message) => {
  if (!source.includes(value)) fail(message);
};

const service = read('src/services/tibiaMap.ts');
const page = read('src/pages/TibiaMapPage.tsx');
const viewer = read('src/components/map/TibiaMapViewer.tsx');
const metadataPanel = read('src/components/MapMetadataPanel.tsx');
const questInsets = read('src/components/quest/QuestMapInsets.tsx');
const huntDetail = read('src/pages/HuntZoneDetailPage.tsx');
const styles = read('src/index.css');
const translations = read('src/i18n.ts');
const api = read('../backend/app/api/v1/tibia_map.py');

for (const state of ['resolved_point', 'resolved_area', 'knowledge_only', 'unresolved']) {
  requireText(service, state, `canonical result contract is missing ${state}`);
}
requireText(service, 'canonical_entity_id', 'canonical map result identity is missing');
requireText(service, 'async layer(layer:', 'lazy layer client is missing');
requireText(service, 'buildMapEntityUrl', 'detail-to-map URL contract is missing');
if (/\bapi\.(post|put|patch|delete)\b/.test(service)) fail('map client must remain a read-only Knowledge consumer');

requireText(page, 'tibiaMapApi.layer(', 'map page does not lazy-load independent layers');
requireText(page, 'if (next.has(layer)) next.delete(layer)', 'layer toggles are not independent');
requireText(page, 'setSearchError(true)', 'search failure is not distinct from no matches');
requireText(page, 'focusBounds=', 'area selection does not request fit-bounds behavior');
requireText(page, 'if (evidence?.z != null && evidence.z !== floor) setFloor(evidence.z)', 'result selection does not switch to the trusted floor');
requireText(page, "kind: 'group'", 'exact-position overlaps are not grouped');
requireText(page, 'onMarkerSelect=', 'layer markers cannot select their canonical result');
requireText(page, 'aria-pressed={activeLayers.has(layer)}', 'layer toggle state is not exposed accessibly');
requireText(page, 'aria-live="polite"', 'search/layer status lacks an accessible live region');
requireText(page, 'h-[calc(100dvh', 'map does not retain the bounded mobile viewport contract');

requireText(viewer, 'FocusViewport', 'point/area focus controller is missing');
requireText(viewer, 'maxZoom: 3', 'fit-bounds lacks a large-area zoom guard');
requireText(viewer, 'MapMarkerKind', 'semantic marker kinds are missing');
requireText(metadataPanel, 'buildMapEntityUrl', 'Creature/NPC/Location detail-to-map contract is missing');
requireText(questInsets, 'canonicalEntityId: entityId', 'Quest detail-to-map link omits canonical identity');
requireText(huntDetail, 'canonicalEntityId: zone.knowledge_entity_id', 'Hunt detail-to-map link omits canonical identity');
const markerStyles = styles.slice(styles.indexOf('.tibia-map-entity-marker'));
if (/#[0-9a-f]{3,8}\b|rgba?\(/i.test(markerStyles)) fail('Phase 3D marker styles contain raw colors');
for (const kind of ['location', 'npc', 'quest', 'boss', 'hunt_zone', 'group']) {
  requireText(markerStyles, `--${kind}`, `marker system does not distinguish ${kind}`);
}

requireText(api, 'MAP_LAYERS', 'backend layer allow-list is missing');
requireText(api, '@router.get("/layers/{layer}")', 'bounded layer endpoint is missing');
requireText(api, 'HuntZone.knowledge_entity_id.isnot(None)', 'legacy HuntZones are not excluded from canonical map discovery');
requireText(api, 'SpatialEntityLocationLink.verification_state.in_({"unresolved", "ambiguous"})', 'unresolved spatial state is not preserved');
requireText(api, '"role": "obtained_from"', 'Item map evidence lacks relationship context');
requireText(api, 'HuntZone.knowledge_entity_id.isnot(None)', 'Creature Spawn compatibility is not restricted to canonical HuntZones');

for (const key of ['defaultLocations', 'spatialUnresolved', 'layerFailed', 'markerGroup', 'selectedEntity']) {
  if ((translations.match(new RegExp(`"${key}"`, 'g')) || []).length < 2) fail(`translation parity is missing ${key}`);
}

if (!process.exitCode) {
  console.log('Phase 3D checks passed: canonical results, exact spatial states, independent lazy layers, safe focus, read-only map behavior, accessibility, and semantic theme markers are present.');
}
