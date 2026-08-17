import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const navigationUtility = new URL('../src/utils/cyclopediaNavigation.ts', import.meta.url).pathname;
const bundle = await build({ entryPoints: [navigationUtility], bundle: true, format: 'esm', platform: 'node', write: false });
const moduleUrl = `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`;
const navigation = await import(moduleUrl);

assert.equal(navigation.buildKnowledgeSearchPath('items', 'Legio'), '/cyclopedia?tab=loot&q=Legio');
assert.equal(navigation.buildKnowledgeSearchPath('bosses', 'Morshabaal'), '/cyclopedia?tab=bosses&q=Morshabaal');
assert.equal(navigation.buildKnowledgeSearchPath('zones', 'Roshamuul'), '/cyclopedia?tab=zones&q=Roshamuul');

const page = read('src/pages/CreaturesPage.tsx');
const search = read('src/components/search/KnowledgeSearchBox.tsx');
const itemBrowser = read('src/services/itemBrowser.ts');
const navigationMenu = read('src/components/Navigation.tsx');
const home = read('src/pages/HomePage.tsx');
const categoryIcon = read('src/components/knowledge/KnowledgeCategoryIcon.tsx');
const itemDetail = read('src/pages/ItemDetailPage.tsx');
const zoneDetail = read('src/pages/HuntZoneDetailPage.tsx');
const mapViewer = read('src/components/map/TibiaMapViewer.tsx');

assert.match(search, /buildKnowledgeSearchPath\(section, query\)/, 'Enter/search submission must retain the selected section');
assert.match(page, /getPopularBosses/, 'Boss carousel must use the real popularity endpoint');
assert.match(page, /mode === 'bosses'[\s\S]*?<CompactEntityStrip/, 'Bosses must use the horizontal entity rail');
assert.doesNotMatch(page, /cyclopedia\.helpers\.bosses/, 'redundant Boss helper banner must be removed');
assert.doesNotMatch(page, /mode === 'bosses'[\s\S]{0,220}<CyclopediaDiscovery/, 'Bosses must not render the duplicate discovery heading');

assert.match(
  page,
  /origin\.getBoundingClientRect\(\)\.top <= readStickyOffsetPx\(\)/,
  'sticky Cyclopedia search must use its stable origin instead of result-card boundaries',
);
assert.match(
  page,
  /window\.addEventListener\('scroll', updateCompactState, \{ passive: true \}\)/,
  'sticky Cyclopedia search must react to passive window scrolling',
);
assert.doesNotMatch(
  page,
  /scrollingDownRef|lastScrollYRef|COMPACT_ACTIVATE_MARGIN_PX/,
  'sticky search must not depend on scroll direction or a second-result activation boundary',
);
assert.doesNotMatch(
  page,
  /transition-\[top,transform,opacity\]|transition-\[max-height,opacity,transform,margin\]/,
  'sticky search must not animate layout/position when compacting',
);
assert.match(
  page,
  /const canAutoPaginate =[\s\S]*?mode === 'creatures' \|\|[\s\S]*?mode === 'bosses' \|\|[\s\S]*?mode === 'items' \|\|[\s\S]*?effectiveSearchTerm\.trim\(\)\.length > 0/,
  'Creatures, Bosses, and Loot must paginate even when their browse query is empty',
);
assert.doesNotMatch(
  page,
  /errorMessage \|\|\s*!effectiveSearchTerm\.trim\(\)/,
  'empty search text must not disable the infinite-scroll observer',
);

assert.match(itemBrowser, /api\.get\('\/items\/browse'/, 'Loot must browse the canonical local item endpoint');
assert.match(itemBrowser, /api\.get\('\/items\/facets'/, 'Loot category controls must come from local canonical facets');
assert.match(page, /mode === 'items'[\s\S]*?itemBrowserApi\.browse\(/, 'Loot mode must load browse results without requiring typed search text');
assert.match(page, /itemBrowserApi\s*\.\s*getFacets\(/, 'Loot mode must load category facets');
assert.match(page, /setItemCategory\(event\.target\.value\)/, 'Loot must expose category filtering');
assert.match(page, /setItemSort\(event\.target\.value as ItemBrowseSort\)/, 'Loot must expose sort selection');
assert.doesNotMatch(
  page,
  /mode === 'items' &&\s*effectiveSearchTerm\.trim\(\)\.length > 1 &&\s*items\.map/,
  'Loot result cards must not disappear when the search box is empty',
);

for (const [name, source] of [['Navigation', navigationMenu], ['Home', home], ['Cyclopedia', page]]) {
  assert.match(source, /KnowledgeCategoryIcon/, `${name} must use the shared category visual component`);
}
assert.match(categoryIcon, /\/catalog\/category-visuals/, 'category visuals must come from one local registry endpoint');

assert.match(itemDetail, /\/creatures\/\$\{creatureRoute\}/, 'item drop creatures must be navigable');
assert.match(itemDetail, /\/hunt-zones\/\$\{zone\.slug \|\| zone\.id\}/, 'item drop hunt zones must be navigable');
assert.doesNotMatch(itemDetail, /dropFacts|common\.unknown/, 'item acquisition cards must omit repetitive unknown facts');

assert.doesNotMatch(zoneDetail, /futureMap|noPremium|noQuest/, 'hunt-zone detail must not ship future-map or repeated negative placeholders');
assert.match(mapViewer, /L\.CRS\.Simple/, 'map must use image coordinates rather than geographic projection');
assert.match(mapViewer, /ImageOverlay/, 'map must use the fetched local image');
assert.match(mapViewer, /map\.zoomIn\(\)|map\.zoomOut\(\)|map\.fitBounds/, 'map zoom and reset controls must exist');
assert.doesNotMatch(mapViewer, /TileLayer|tibiamaps\.github|google|openstreetmap/i, 'map viewer must not request an external tile provider');

for (const source of [page, itemDetail, zoneDetail, mapViewer]) {
  assert.doesNotMatch(source, /(?:min-w|w)-\[(?:32[1-9]|3[3-9]\d|[4-9]\d\d|\d{4,})px\]/, 'Cyclopedia mobile surfaces must not impose page-width overflow');
}

console.log('Cyclopedia interaction checks passed: stable sticky search, infinite scrolling, browsable Loot, category visuals, Boss sorting/carousel state, tab-preserving Enter, item links, local map controls, and mobile guards are present.');
