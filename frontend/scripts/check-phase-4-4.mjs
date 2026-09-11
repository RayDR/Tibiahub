import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const home = read('src/pages/HomePage.tsx');
const api = read('src/services/api.ts');
const types = read('src/types/index.ts');
const i18n = read('src/i18n.ts');
const backend = read('../backend/app/services/boosted_creatures_service.py');
const boostedContext = read('src/components/cyclopedia/BoostedCreatureContext.tsx');
const creatureCard = read('src/components/CreatureCard.tsx');
const workspace = read('src/components/cyclopedia/CyclopediaCreatureWorkspace.tsx');
const appTabs = read('src/components/ui/AppTabs.tsx');
const previewStyles = read('src/styles/cyclopedia-preview-behavior.css');
const cardPolish = read('src/styles/cyclopedia-card-polish.css');
const indexCss = read('src/index.css');

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

assert.match(boostedContext, /tibiaApi\s*\.getBoosted\(controller\.signal\)/, 'Cyclopedia must use the authoritative boosted projection');
assert.match(boostedContext, /projection\.resolution_state !== 'resolved'/, 'Cyclopedia must not pin unresolved boosted entities');
assert.match(workspace, /BoostedCreatureGridPin/, 'Cyclopedia workspace must pin resolved boosted Creature and Boss entries');
assert.match(workspace, /data-cyclopedia-boosted-pin/, 'the injected boosted entry must be identifiable and deduplicated');
assert.match(creatureCard, /data-boosted=\{isBoosted \? 'true' : 'false'\}/, 'boosted cards must expose semantic UI state');
assert.match(creatureCard, /order: isBoosted \? -1 : undefined/, 'a boosted entity already present in results must remain first');
assert.match(previewStyles, /--cyclopedia-boosted-rgb: var\(--ds-accent\)/, 'Cyclopedia boosted styling must reuse the Home accent treatment');
assert.match(previewStyles, /rgb\(var\(--ds-danger\) \/ 0\.92\)/, 'boosted styling must keep an alternate edge when accent and primary converge');

assert.match(appTabs, /cyclopediaMode != null && cyclopediaMode !== 'creatures'/, 'Creature tabs must not share a wrapper with the personal-history strip that legacy CSS hides');
assert.match(appTabs, /data-variant=\{isCyclopediaTabs \? 'cyclopedia' : undefined\}/, 'Cyclopedia tablist must retain its stable variant hook');

assert.match(workspace, /cardCenter >= gridCenter \? 'left' : 'right'/, 'desktop preview must open opposite the selected card');
assert.match(workspace, /data-preview-side=\{side\}/, 'preview side must be exposed to responsive styling');
assert.match(workspace, /--cyclopedia-preview-card-left/, 'preview portal must expose the selected card left edge');
assert.match(workspace, /--cyclopedia-preview-card-right/, 'preview portal must expose the selected card right edge');
assert.match(workspace, /--cyclopedia-preview-anchor-top/, 'preview portal must expose a selected-card vertical anchor');
assert.match(previewStyles, /data-cyclopedia-preview-side='left'/, 'wide layout must reserve space for a left-side preview');
assert.match(previewStyles, /data-cyclopedia-preview-side='right'/, 'wide layout must reserve space for a right-side preview');
assert.match(previewStyles, /left: calc\(var\(--cyclopedia-preview-card-right\) \+ var\(--space-3\)\)/, 'compact cards on the left must open their preview immediately to the right');
assert.match(previewStyles, /right: calc\(100vw - var\(--cyclopedia-preview-card-left\) \+ var\(--space-3\)\)/, 'compact cards on the right must open their preview immediately to the left');
assert.match(previewStyles, /top: var\(--cyclopedia-preview-anchor-top, var\(--cyclopedia-preview-top\)\)/, 'compact preview must align vertically with the selected card while respecting sticky controls');
assert.match(previewStyles, /bottom: auto;/, 'desktop preview dock must not be stretched by simultaneous top and bottom positioning');
assert.match(previewStyles, /cyclopedia-creature-preview-sticky[\s\S]*max-height: calc\(/, 'preview content must use the measured lower inset only as a max-height boundary');
assert.match(previewStyles, /cyclopedia-creature-preview-sticky[\s\S]*box-shadow: var\(--elevation-overlay\)/, 'preview shadow must belong to the rendered preview surface instead of the viewport-height dock');
assert.match(previewStyles, /html\[data-motion='reduced'\] \.cyclopedia-creature-preview-dock/, 'Appearance reduced motion must disable preview entrance animation');
assert.match(previewStyles, /html\[data-motion='enhanced'\].*data-preview-side='left'/s, 'Appearance enhanced motion must animate lateral preview entrance');

assert.match(indexCss, /cyclopedia-card-polish\.css/, 'entity card polish must load after entity-specific Cyclopedia styles');
assert.match(cardPolish, /\.loot-cyclopedia-card__crest[\s\S]*left: 0\.05rem/, 'Loot representative icon must live on the top-left edge');
assert.match(cardPolish, /\.loot-cyclopedia-card__details[\s\S]*right: 0\.45rem/, 'Loot direct-detail action must stay top-right');
assert.match(cardPolish, /\.npc-cyclopedia-card__crest[\s\S]*left: 0\.05rem/, 'NPC representative icon must live on the top-left edge');
assert.match(cardPolish, /\.npc-cyclopedia-card__details[\s\S]*top: 0\.52rem[\s\S]*right: 0\.52rem/, 'NPC direct-detail action must move to the top-right edge');
assert.match(previewStyles, /repeat\(6, minmax\(0, 1fr\)\)/, 'large Wide Creature/Boss grids must expose additional cards');
assert.match(previewStyles, /repeat\(7, minmax\(0, 1fr\)\)/, 'extra-large Wide Creature/Boss grids must expose additional cards');
assert.match(cardPolish, /html\[data-layout='wide'\] \.loot-cyclopedia-grid[\s\S]*repeat\(6, minmax\(0, 1fr\)\)/, 'large Wide Loot grids must expose additional cards');
assert.match(cardPolish, /html\[data-layout='wide'\] \.loot-cyclopedia-grid[\s\S]*repeat\(7, minmax\(0, 1fr\)\)/, 'extra-large Wide Loot grids must expose additional cards');

for (const category of ['creatures', 'bosses', 'items', 'quests', 'zones', 'npcs']) {
  assert.match(home, new RegExp(`key: '${category}'`), `Home must retain the ${category} card`);
}
assert.match(home, /to: '\/cyclopedia\?tab=creatures'/);
assert.match(home, /to: '\/cyclopedia\?tab=bosses'/);
assert.equal((i18n.match(/"boosted": \{ "badge": "BOOSTED"/g) || []).length, 2, 'BOOSTED copy must exist in EN and ES');
assert.doesNotMatch(home, /#[0-9a-f]{3,8}\b/i, 'Home boosted treatment must not add raw colors');
assert.doesNotMatch(previewStyles, /#[0-9a-f]{3,8}\b/i, 'Cyclopedia preview and boosted treatment must use design tokens');
assert.doesNotMatch(cardPolish, /#[0-9a-f]{3,8}\b/i, 'Cyclopedia card polish must use design tokens');

console.log('Phase 4.4 checks passed: authoritative boosted states enrich Home and Cyclopedia, Creature tabs remain visible, compact previews anchor beside the selected card, and desktop card density/corners remain consistent.');
