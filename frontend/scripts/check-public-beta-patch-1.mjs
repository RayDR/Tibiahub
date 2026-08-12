import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const [map, cyclopedia, quests, navigation, notifications, adminUsers, members, planner, i18n] = await Promise.all([
  read('src/pages/TibiaMapPage.tsx'),
  read('src/pages/CreaturesPage.tsx'),
  read('src/components/QuestLibraryShelves.tsx'),
  read('src/components/Navigation.tsx'),
  read('src/pages/guild/Notifications.tsx'),
  read('src/pages/Admin/Users.tsx'),
  read('src/pages/guild/Members.tsx'),
  read('src/pages/HuntRecommendationsPage.tsx'),
  read('src/i18n.ts'),
]);

assert.match(map, /setResults\(\[\]\)/, 'map must not populate the result panel before search');
assert.match(map, /bootstrap\?\.towns\.map/, 'empty map search must expose imported towns');
assert.match(map, /h-\[calc\(100dvh/, 'map must own the available viewport');
assert.match(map, /huntZoneContext/, 'hunt selection must load contextual pins and routes');
assert.match(map, /selectResult\(row\)/, 'entity results must drive map selection');

assert.match(cyclopedia, /itemsApi\.getPopular/);
assert.match(cyclopedia, /itemsApi\.getTrending/);
assert.match(cyclopedia, /cyclopedia\.discovery\.trendingLoot/);
assert.match(quests, /lg:grid-cols-\[minmax\(0,7fr\)_minmax\(16rem,3fr\)\]/);
assert.ok(quests.indexOf('const allTime') < quests.indexOf('const personal'), 'all-time shelf must own its entries first');

assert.match(navigation, /shortLabel: t\('nav\.planner'\)/);
assert.match(navigation, /shortLabel: t\('nav\.map'\)/);
assert.match(navigation, /lg:hidden/);
assert.match(navigation, /iconOnly: true/);

assert.match(cyclopedia, /resultBlocks\[1\]/, 'sticky boundary must use the second result block');
assert.match(cyclopedia, /IntersectionObserver/);
assert.match(cyclopedia, /scrollingDownRef\.current/);
assert.doesNotMatch(cyclopedia, /isSearchPreparing|compactTimerRef/, 'timer/preparing state machine must remain removed');

assert.match(notifications, /notificationApi\.list\(items\.length, 20\)/);
assert.match(adminUsers, /<table/);
assert.match(adminUsers, /getUsers\(0, 50/);
assert.match(adminUsers, /getUsers\(users\.length, 50/);
assert.match(members, /<MemberDetail/);
assert.match(members, /member\.linked_email/);

for (const field of ['suggested_level', 'raw_creature_exp', 'valuable_loot', 'weaknesses', 'resistances']) {
  assert.ok(planner.includes(field), `planner recommendation cards must expose ${field}`);
}
assert.match(planner, /const PAGE_SIZE = 6/);
assert.match(planner, /IntersectionObserver/, 'Planner must incrementally load recommendations');
assert.match(planner, /aria-modal="true"/, 'Planner map/details must open in a modal');
for (const phrase of ['Quick searches', 'Previous results', 'Next results', 'Inspect Zone', 'Find Hunting Spots', 'Loading zone details', 'No suitable hunt zones']) {
  assert.ok(!map.includes(phrase) && !planner.includes(phrase) && !navigation.includes(phrase), `player prose must use i18n: ${phrase}`);
}
assert.match(i18n, /"map": "Map"/);
assert.match(i18n, /"map": "Mapa"/);
assert.doesNotMatch(i18n, /"map": "(?:Tibia Map|Mapa de Tibia)"/);

console.log('Public beta patch 1 checks passed: Planner, map, shelves, navigation, sticky transition, pagination, admin table, and member detail contracts are present.');
