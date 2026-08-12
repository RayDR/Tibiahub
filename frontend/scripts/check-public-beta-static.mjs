import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const app = read('src/App.tsx');
const cyclopedia = read('src/pages/CreaturesPage.tsx');
const creature = read('src/pages/CreatureDetailPage.tsx');
const quest = read('src/pages/QuestDetailPage.tsx');
const feedback = read('src/components/feedback/GitHubFeedbackLink.tsx');
const seo = read('src/utils/seo.ts');
const translations = read('src/i18n.ts');
const nginx = read('../nginx-tibiahub.conf');

for (const route of ['/items/:identifier', '/hunt-zones/:identifier']) assert.ok(app.includes(route), `missing public route ${route}`);
assert.match(cyclopedia, /to: `\/items\//, 'item suggestions must use detail routes');
assert.match(cyclopedia, /to: `\/hunt-zones\//, 'hunt-zone suggestions must use detail routes');
assert.match(creature, /spawn_locations\.length > 0/, 'creatures must prefer structured spawn relationships');
assert.match(creature, /\/hunt-zones\//, 'creature spawn cards must link to hunt zones');
assert.doesNotMatch(creature, /missing_fields|data_sources/, 'maintainer diagnostics must not render on creature detail');
assert.match(quest, /id="missions"/, 'quest codex must expose mission chapter navigation');
assert.doesNotMatch(quest, /referencesPending/, 'unresolved diagnostics must not render in the player footer');
assert.doesNotMatch(translations, /PostgreSQL|PostGIS|Grounded conversational assistant|Asistente conversacional fundamentado/, 'player copy must not expose infrastructure language');
assert.match(feedback, /knowledge-data-correction\.yml/, 'entity corrections must open the dedicated Issue Form');
assert.match(feedback, /Nothing is sent until you submit/, 'feedback must remain explicitly user-submitted');
assert.match(seo, /noindex, nofollow/, 'private routes need a noindex policy');
assert.match(seo, /BreadcrumbList/, 'public detail SEO must support structured breadcrumbs');
assert.match(nginx, /location = \/sitemap\.xml/, 'Nginx must expose the root sitemap');
assert.match(nginx, /location = \/robots\.txt/, 'Nginx must expose root robots.txt');

console.log('Public beta static checks passed: canonical routes, relationship UX, player-safe detail copy, feedback, and SEO delivery are present.');
