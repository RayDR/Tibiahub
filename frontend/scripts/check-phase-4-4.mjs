import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const home = read('src/pages/HomePage.tsx');
const api = read('src/services/api.ts');
const types = read('src/types/index.ts');
const i18n = read('src/i18n.ts');
const backend = read('../backend/app/services/boosted_creatures_service.py');

assert.match(home, /tibiaApi\s*\.getBoosted\(controller\.signal\)/, 'Home must request the TibiaHub boosted endpoint after mount');
assert.match(api, /api\.get<TibiaBoostedResponse>\('\/tibia\/boosted', \{ signal \}\)/, 'frontend service must use only /api/v1/tibia/boosted');
assert.doesNotMatch(home, /api\.tibiadata\.com|static\.tibia\.com|image_url/i, 'Home must not use provider URLs or media fields');
assert.doesNotMatch(api, /api\.tibiadata\.com|static\.tibia\.com/, 'frontend API service must not contact upstream directly');
assert.match(backend, /\/api\/v1\/creatures\/\{creature\.id\}\/image\?placeholder=false/, 'boosted media must use the verified local Creature route');
assert.match(home, /option\.key === 'creatures'/, 'Creature card must receive its BOOSTED state');
assert.match(home, /option\.key === 'bosses'/, 'Boss card must receive its BOOSTED state');
assert.match(home, /resolution_state === 'unavailable'/, 'unavailable upstream data must preserve the generic card');
assert.match(home, /current\?\.source_name/, 'unresolved entities must retain their authoritative source name');
assert.match(home, /onError=\{\(\) => setImageFailed\(true\)\}/, 'boosted image must have a local fallback');
assert.match(types, /'resolved' \| 'unresolved' \| 'unavailable'/, 'frontend types must preserve resolution state');

for (const category of ['creatures', 'bosses', 'items', 'quests', 'zones', 'npcs']) {
  assert.match(home, new RegExp(`key: '${category}'`), `Home must retain the ${category} card`);
}
assert.match(home, /to: '\/cyclopedia\?tab=creatures'/);
assert.match(home, /to: '\/cyclopedia\?tab=bosses'/);
assert.equal((i18n.match(/"boosted": \{ "badge": "BOOSTED"/g) || []).length, 2, 'BOOSTED copy must exist in EN and ES');
assert.doesNotMatch(home, /#[0-9a-f]{3,8}\b/i, 'Home boosted treatment must not add raw colors');

console.log('Phase 4.4 checks passed: authoritative boosted states enrich only Creature and Boss Home cards with verified local media.');
