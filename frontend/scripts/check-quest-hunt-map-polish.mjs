import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const questCards = read('src/components/QuestLibraryShelves.tsx');
const questPreview = read('src/components/cyclopedia/QuestPreviewPanel.tsx');
const planner = read('src/pages/HuntRecommendationsPage.tsx');
const map = read('src/pages/TibiaMapPage.tsx');
const polish = read('src/styles/quest-hunt-map-polish.css');
const index = read('src/index.css');

assert.match(questCards, /BrandCategoryFallbackIcon category="quests"/, 'Quest cards must use the design fallback icon by default');
assert.doesNotMatch(questCards, /quest\.image_url/, 'Quest list cards must not depend on optional admin preview artwork');
assert.match(questPreview, /src=\{quest\.image_url\}/, 'Admin-provided quest artwork must be consumed by the quest preview');
assert.match(questPreview, /fallbackKind="quest"/, 'Quest preview must fall back safely when no artwork exists');

assert.match(planner, /BrandNavigationIcon icon="planner"/, 'Hunt Planner header must use the shared branded planner icon');
assert.match(planner, /hunt-planner-preview__close/, 'Hunt Planner preview must expose a close control');
assert.match(planner, /onClick=\{\(\) => setSelected\(null\)\}/, 'Hunt Planner preview close must release the selected hunt');
assert.match(planner, /hunt-planner-result__identity/, 'Hunt result name and place must use a vertical identity stack');
assert.match(planner, /hunt-planner-result__risk-cell/, 'Hunt risk must have an explicit alignment cell');
assert.match(polish, /\.hunt-planner-results\s*\{[\s\S]*max-height:[\s\S]*overflow: auto/, 'Hunt results must scroll inside a viewport-bounded region');
assert.match(polish, /scrollbar-width: none/, 'Workspace internal scrolling must keep scrollbars visually hidden');
assert.match(polish, /\.hunt-planner-results__head > span\s*\{[\s\S]*text-align: center/, 'Planner table headings must be centered by default');

assert.match(map, /const \[selectedCity, setSelectedCity\] = useState\('Thais'\)/, 'Map city filter must default to Thais');
assert.match(map, /cityOptions\.map/, 'Map city filter must expose all authoritative bootstrap towns');
assert.match(map, /map-search-sidebar/, 'Map search results must render in a secondary sidebar');
assert.match(map, /map-workspace--search-open/, 'Map workspace must reserve or overlay search-sidebar space explicitly');
assert.match(polish, /\.app-shell-main-map\s*\{[\s\S]*height: 100dvh/, 'Map shell must be constrained to the viewport');
assert.match(polish, /\.tibia-map-page\s*\{[\s\S]*overflow: hidden/, 'Map page must not create document scrolling');
assert.match(polish, /\.map-compass\s*\{[\s\S]*left: 50%/, 'Compass must stay clear of the top-right viewer controls');
assert.match(index, /quest-hunt-map-polish\.css/, 'Loop-two workspace polish must be loaded globally');

console.log('Quest/Hunt/Map polish checks passed.');
