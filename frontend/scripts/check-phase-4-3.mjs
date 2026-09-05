import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const importBundled = async path => {
  const entry = new URL(`../${path}`, import.meta.url).pathname;
  const bundle = await build({ entryPoints: [entry], bundle: true, format: 'esm', platform: 'node', write: false });
  const url = `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`;
  return import(url);
};

const sectionsModule = await importBundled('src/config/cyclopediaSections.ts');
const npcModule = await importBundled('src/utils/npcCyclopedia.ts');
const navigationModule = await importBundled('src/utils/cyclopediaNavigation.ts');

const { cyclopediaSections, modeToTab, tabToMode } = sectionsModule;
const {
  NPC_CYCLOPEDIA_PAGE_SIZE,
  buildLegacyNpcBrowseRedirect,
  localNpcMediaUrl,
  mergeNpcRows,
  npcPageHasMore,
} = npcModule;
const { buildCyclopediaPath } = navigationModule;

assert.deepEqual(
  cyclopediaSections.map(section => section.key),
  ['creatures', 'bosses', 'loot', 'quests', 'zones', 'npcs'],
  'NPCs must be the native Cyclopedia tab immediately after Hunt Zones',
);
assert.equal(tabToMode('npcs'), 'npcs', 'the NPC tab must initialize NPC mode');
assert.equal(modeToTab('npcs'), 'npcs', 'NPC mode must round-trip to its canonical tab');
assert.equal(NPC_CYCLOPEDIA_PAGE_SIZE, 20, 'NPC browsing must use the bounded Cyclopedia page size');

const first = { canonical_id: 'npc-a', name: 'A' };
const duplicate = { canonical_id: 'npc-a', name: 'Duplicate A' };
const second = { canonical_id: 'npc-b', name: 'B' };
assert.deepEqual(
  mergeNpcRows([first], [duplicate, second]).map(row => row.canonical_id),
  ['npc-a', 'npc-b'],
  'infinite loading must deduplicate by canonical_id',
);
assert.equal(npcPageHasMore({ skip: 20, items: Array(20), total: 41 }), true, 'returned row count must advance the bounded cursor');
assert.equal(npcPageHasMore({ skip: 40, items: Array(1), total: 41 }), false, 'pagination must stop at the backend total');

assert.equal(localNpcMediaUrl({ status: 'available', url: '/api/v1/npcs/npc-a/image' }), '/api/v1/npcs/npc-a/image');
assert.equal(localNpcMediaUrl({ status: 'cached', url: '/api/v1/npcs/npc-a/image' }), '/api/v1/npcs/npc-a/image', 'deployed cached-media status must remain compatible');
assert.equal(localNpcMediaUrl({ status: 'unavailable', url: '/api/v1/npcs/npc-a/image' }), null, 'known-unavailable media must use the placeholder');
assert.equal(localNpcMediaUrl({ status: 'available', url: 'https://provider.example/npc.gif' }), null, 'provider media URLs must never render');

assert.equal(buildLegacyNpcBrowseRedirect(''), '/cyclopedia?tab=npcs');
assert.equal(buildLegacyNpcBrowseRedirect('?q=banker&location=Thais&page=4'), '/cyclopedia?tab=npcs&q=banker&location=Thais', 'legacy q/location must survive while numbered page is dropped');
assert.equal(
  buildCyclopediaPath({ tab: 'npcs', q: 'banker', location: 'Thais' }),
  '/cyclopedia?tab=npcs&q=banker&location=Thais',
  'NPC query and location must round-trip through Cyclopedia URL state',
);
assert.equal(buildCyclopediaPath({ tab: 'creatures', q: 'dragon' }), '/cyclopedia?tab=creatures&q=dragon', 'unrelated tabs must not acquire an NPC location filter');

const page = read('src/pages/CreaturesPage.tsx');
assert.match(page, /tabToMode\(tabParam\).*\|\| 'creatures'/s, 'direct /cyclopedia?tab=npcs must initialize through the central tab contract');
assert.match(page, /namedKnowledgeApi\.listNpcs\([\s\S]*?search: normalized \|\| undefined,[\s\S]*?location: cacheLocation \|\| undefined,[\s\S]*?skip: nextSkip,[\s\S]*?limit: PAGE_SIZE/, 'NPC browse/search/location must use one bounded backend request');
assert.match(page, /mode === 'npcs'[\s\S]*?\? true[\s\S]*?: mode === 'quests'/, 'NPC no-query browse must still fetch its first page');
assert.match(page, /setTimeout\(\(\) => \{\s*void performSearch\(true\);\s*\}, 450\)/, 'NPC query/location changes must use the Cyclopedia debounce');
assert.match(page, /activeRequestRef\.current\?\.abort\(\)/, 'changed queries must cancel stale requests');
assert.match(page, /controller\.signal\.aborted \|\| activeRequestRef\.current !== controller/, 'stale responses must not overwrite current state');
assert.match(page, /loadMoreLockRef\.current = true/, 'infinite loading must lock duplicate active requests');
assert.match(page, /setSkip\(page\.skip \+ page\.items\.length\)/, 'the next NPC cursor must advance by the returned count');
assert.match(page, /mergeNpcRows\(npcs, page\.items\)/, 'subsequent NPC pages must use canonical deduplication');
assert.match(page, /mode === 'npcs' \? npcLocation\.trim\(\) : ''/, 'location must be isolated to NPC mode');
assert.match(page, /setNpcLocation\(nextNpcLocation\)/, 'browser navigation must restore the NPC location filter');
assert.match(page, /setNpcLocation\(''\)/, 'clearing/switching tabs must clear the NPC location filter');
assert.match(page, /location: mode === 'npcs' \? npcLocation : ''/, 'URL and snapshot state must include location only for NPC mode');
assert.match(page, /cacheGet<CyclopediaCachedResults>/, 'NPC results must participate in the existing cache restore flow');
assert.match(page, /npcs: merged/, 'loaded NPC pages must be saved together for detail-return restoration');
assert.match(page, /loadMoreSentinelRef/, 'NPC results must reuse the shared IntersectionObserver sentinel');
assert.match(page, /externalSuggestions=\{\s*searchSuggestions\s*\}/, 'NPC suggestions must be built from currently loaded rows');
assert.doesNotMatch(page, /popularNPC|popularNpc|trendingNPC|trendingNpc/, 'default NPC rows must not be presented as popularity data');

const card = read('src/components/NpcCard.tsx');
assert.match(card, /`\/npcs\/\$\{npc\.canonical_id\}`/, 'NPC cards must retain canonical detail links');
assert.match(card, /buildMapEntityUrl\(\{[\s\S]*?entityType: 'npc',[\s\S]*?canonicalEntityId: npc\.canonical_id,[\s\S]*?name: npc\.name,[\s\S]*?slug: npc\.slug/, 'NPC cards must retain exact map-link inputs');
assert.match(card, /loading="lazy"/, 'local NPC media must be lazy-loaded');
assert.match(card, /decoding="async"/, 'local NPC media must decode asynchronously');
assert.match(card, /\[image-rendering:pixelated\]/, 'NPC sprites must retain pixel rendering');
assert.match(card, /onError=\{\(\) => setFailed\(true\)\}/, 'a missing local file must degrade to the placeholder');
assert.doesNotMatch(card, /source_url|fandom|https?:\/\//i, 'NPC cards must not use provider media or guessed URLs');

const app = read('src/App.tsx');
assert.match(app, /path="\/npcs" element=\{<Navigate to=\{buildLegacyNpcBrowseRedirect\(location\.search\)\} replace \/>\}/, 'legacy NPC browse must redirect compatibly');
assert.match(app, /path="\/npcs\/:identifier" element=\{<NpcDetailPage \/>\}/, 'NPC detail route must remain unchanged');
assert.doesNotMatch(app, /NpcDirectoryPage/, 'the retired directory must not remain a routed browse surface');

const cache = read('src/services/cyclopediaCache.ts');
assert.match(cache, /location\?: string/, 'cache/snapshot contracts must support NPC location');
assert.match(cache, /params\.location \|\| ''/, 'cache identity must separate NPC location filters');

console.log('Phase 4.3 checks passed: native NPC tab, bounded browse/search, safe pagination, local media, compatibility redirects, and cache/location restoration.');
