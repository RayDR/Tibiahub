import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const utilityPath = new URL('../src/utils/tibiaMapSelection.ts', import.meta.url).pathname;
const bundle = await build({ entryPoints: [utilityPath], bundle: true, format: 'esm', platform: 'node', write: false });
const moduleUrl = `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`;
const { markersForMapMode, requestedMapSelection, resolveMapSearchSelection } = await import(moduleUrl);

const edron = { id: 'location:edron', entity_type: 'location', canonical_entity_id: 'edron-id', slug: 'edron' };
const thaisGuide = { id: 'npc:guide', entity_type: 'npc', canonical_entity_id: 'guide-id', slug: 'thais-guide' };

assert.equal(
  resolveMapSearchSelection([edron, thaisGuide], requestedMapSelection(new URLSearchParams('q=Missing&entityType=npc&entity=missing-id&slug=missing'))),
  null,
  'an invalid deep link must not fall back to Edron or another result',
);
assert.equal(
  resolveMapSearchSelection([edron, thaisGuide], requestedMapSelection(new URLSearchParams('q=Thais+Guide&entityType=npc&entity=guide-id&slug=thais-guide'))),
  thaisGuide,
  'a valid deep link must select only its exact requested entity',
);
assert.equal(
  resolveMapSearchSelection([edron, thaisGuide], null),
  edron,
  'ordinary search keeps its existing first-result selection contract',
);

const unrelatedLayerMarkers = [{ id: 'edron-marker' }, { id: 'unrelated-creature-marker' }];
const selectedMarkers = [{ id: 'guide-marker' }];
assert.deepEqual(
  markersForMapMode(true, unrelatedLayerMarkers, selectedMarkers),
  selectedMarkers,
  'selected/filter mode must hide unrelated active-layer markers',
);
assert.deepEqual(
  markersForMapMode(false, unrelatedLayerMarkers, selectedMarkers),
  unrelatedLayerMarkers,
  'clearing selected/filter mode must restore active-layer markers',
);

const page = read('src/pages/TibiaMapPage.tsx');
assert.match(page, /useState<TibiaMapResult \| null>\(null\)/, 'initial map selection must be null');
assert.doesNotMatch(page, /selectResult\(bootstrap\.default_results\[0\]/, 'bootstrap results must never be auto-selected');
assert.doesNotMatch(page, /\|\| combined\[0\]/, 'failed exact deep links must not fall back to a combined result');
assert.match(page, /resolveMapSearchSelection\(combined, searchRequestedSelection\)/, 'search/deep-link resolution must use the exact selection policy');
assert.match(page, /markersForMapMode\(isolatedMarkerMode, layerMarkers, entityMarkers\)/, 'map marker visibility must honor isolated selection/filter mode');
assert.match(page, /internalParamsUpdate/, 'internal URL updates must be distinguished from browser history navigation');
assert.match(page, /setSearchRequestedSelection\(requestedMapSelection\(next\)\);\s*replaceParams\(next\)/, 'an explicit selection must remain exact across floor/bootstrap refreshes');
assert.match(page, /controller\.abort\(\)/, 'stale map requests must remain cancellable');
assert.doesNotMatch(page, /Thais/, 'this phase must not add a guessed Thais camera or anchor');

const utility = read('src/utils/tibiaMapSelection.ts');
assert.doesNotMatch(utility, /\b(?:x|y|z|bounds|geometry)\b/, 'selection policy must not create or infer spatial evidence');

console.log('Map selection checks passed: neutral bootstrap, exact deep links, isolated markers, restored layers, cancellable navigation, and no spatial inference.');
