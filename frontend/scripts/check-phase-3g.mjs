import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8');
const fail = message => {
  console.error(`Phase 3G check failed: ${message}`);
  process.exitCode = 1;
};
const requireText = (source, value, message) => {
  if (!source.includes(value)) fail(message);
};

const directory = read('src/pages/NpcDirectoryPage.tsx');
const detail = read('src/pages/NpcDetailPage.tsx');
const app = read('src/App.tsx');
const navigation = read('src/components/Navigation.tsx');
const apiClient = read('src/services/api.ts');
const types = read('src/types/index.ts');
const endpoint = read('../backend/app/api/v1/npcs_locations.py');
const projection = read('../backend/app/services/npc_projection_service.py');
const mapEndpoint = read('../backend/app/api/v1/tibia_map.py');

requireText(app, 'path="/npcs"', 'canonical NPC directory route is missing');
requireText(app, 'path="/npcs/:identifier"', 'legacy-compatible NPC detail route is missing');
requireText(navigation, "navigate('/npcs')", 'NPC directory is not integrated into Cyclopedia navigation');
requireText(apiClient, "'/npcs/directory'", 'frontend does not use the paginated NPC API');
requireText(types, 'interface NpcDirectoryPage', 'paginated directory contract is untyped');
requireText(directory, 'window.setTimeout', 'directory search is not debounced');
requireText(directory, 'controller.abort()', 'stale directory requests are not cancelled');
requireText(directory, 'PaginationControls', 'directory lacks server pagination controls');
requireText(directory, 'location: requestedLocation', 'supported location filtering is not sent to the server');
requireText(directory, 'npc.canonical_id', 'new detail navigation does not prefer canonical identity');
requireText(directory, 'npc.map_available', 'cards do not distinguish verified map coverage');
requireText(directory, "value == null", 'cards do not distinguish unknown from known-empty counts');
requireText(types, 'npc_buys_from_player', 'NPC-buy semantics are not represented in the detail contract');
requireText(detail, "t('npcDetail.buysHelp')", 'player-facing NPC-buy semantics are not explained');
requireText(detail, "t('npcDetail.sellsHelp')", 'player-facing NPC-sell semantics are not explained');
requireText(detail, 'value.navigation_url', 'canonical item/quest/location links are not rendered');
requireText(detail, 'value.resolution_state', 'unresolved and ambiguous references are not represented');
requireText(detail, 'npc.field_coverage', 'unknown provider fields are not distinguished from empty fields');
requireText(detail, 'locations.length > 1', 'multiple-location state is not disclosed');
requireText(detail, 'MapMetadataPanel', 'Phase 3D spatial projection is not reused');
requireText(detail, "canonicalPath: `/npcs/${npc.canonical_id}`", 'SEO canonical URL does not use canonical identity');
requireText(endpoint, 'class NpcDirectoryPage', 'backend lacks an authoritative paginated response');
requireText(endpoint, 'KnowledgeEntityAlias.normalized_alias.contains', 'safe alias search is missing');
requireText(endpoint, 'TibiaWikiNpc.normalized_name.asc(), TibiaWikiNpc.id.asc()', 'stable NPC ordering is missing');
requireText(endpoint, 'model.knowledge_entity_id == canonical_id', 'detail API does not accept canonical UUIDs');
requireText(projection, 'exact canonical name or verified alias', 'exact relationship resolution contract is undocumented');
requireText(projection, '"ambiguous" if len(matches) > 1 else "unresolved"', 'ambiguous exact matches can be auto-selected');
requireText(projection, '"reference_only" if row.image_url else "missing"', 'unsafe provider media is not classified');
requireText(projection, '_spatial_evidence_by_entity', 'NPC projection does not reuse exact map evidence');
requireText(mapEndpoint, 'navigation_url=f"/npcs/{row.knowledge_entity_id}", image_url=None', 'map results use legacy NPC identity or remote media');
if (/https?:\/\//.test(directory)) fail('directory contains a direct external media URL');
if (/#[0-9a-f]{3,8}\b|rgba?\(/i.test(directory + detail)) fail('NPC UI contains raw colors');
if (/fuzzy|levenshtein|similarity/i.test(projection)) fail('NPC reference projection contains a fuzzy fallback');

if (!process.exitCode) {
  console.log('Phase 3G checks passed: canonical routing, paginated discovery, honest coverage states, exact reference links, safe media, and trusted map reuse are present.');
}
