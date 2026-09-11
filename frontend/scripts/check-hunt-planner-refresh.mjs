import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const page = read('src/pages/HuntRecommendationsPage.tsx');
const styles = read('src/styles/hunt-planner.css');
const activity = read('../backend/app/api/v1/endpoints/me_activity.py');
const index = read('src/index.css');

assert.match(page, /HuntZonePreviewPanel/, 'Hunt Planner must expose the rich Hunt Zone preview');
assert.match(page, /activityApi\.getMine\(40, controller\.signal, activeCharacterId\)/, 'Planner restore must be character scoped');
assert.match(page, /activity_type: 'hunt_search'/, 'Planner searches must persist through activity history');
assert.match(page, /SEARCH_TTL_MS = 7 \* 24 \* 60 \* 60 \* 1000/, 'Guest planner search must expire after one week');
assert.match(page, /sessionStorage\.setItem\(SESSION_KEY/, 'Guest planner search must use session storage');
assert.match(page, /sortedRecommendations/, 'Planner must provide sortable recommendation rows');
assert.match(page, /avg_exp_hour/, 'Recommendation rows must expose XP per hour');
assert.match(page, /avg_profit_hour/, 'Recommendation rows must expose profit per hour');
assert.match(page, /matchPercent\(item\.score\)/, 'Recommendation rows must expose match score');
assert.match(page, /hunt-planner-schedule/, 'Planner must expose the session schedule surface');
assert.match(page, /highlightBoosted/, 'Planner must support boosted-hunt prioritization');

assert.match(styles, /grid-template-columns: minmax\(17\.5rem, 20rem\) minmax\(30rem, 1fr\) minmax\(21rem, 26rem\)/, 'Desktop planner must use setup, recommendations and preview columns');
assert.match(styles, /\.hunt-planner-preview\s*\{[\s\S]*position: sticky/, 'Desktop preview must remain visible while reviewing hunts');
assert.match(styles, /@media \(max-width: 959px\)/, 'Planner must collapse responsively below desktop');
assert.match(index, /hunt-planner\.css/, 'Hunt Planner styles must be loaded globally');

assert.match(activity, /HUNT_SEARCH_TTL = timedelta\(days=7\)/, 'Authenticated hunt searches must expire after seven days');
assert.match(activity, /_replace_hunt_search_for_scope/, 'Authenticated history must keep only the latest hunt search per scope');
assert.match(activity, /UserActivity\.character_id == character_id/, 'Authenticated search state must be character scoped');

console.log('Hunt Planner refresh checks passed: proposal layout, preview, character-scoped restore and seven-day retention are wired.');
