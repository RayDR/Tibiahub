import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const [map, cyclopedia, quests, navigation, notifications, adminUsers, members, planner] = await Promise.all([
  read('src/pages/TibiaMapPage.tsx'),
  read('src/pages/CreaturesPage.tsx'),
  read('src/components/QuestLibraryShelves.tsx'),
  read('src/components/Navigation.tsx'),
  read('src/pages/guild/Notifications.tsx'),
  read('src/pages/Admin/Users.tsx'),
  read('src/pages/guild/Members.tsx'),
  read('src/pages/HuntRecommendationsPage.tsx'),
]);

assert.match(map, /const PAGE_SIZE = 6/);
assert.match(map, /setResults\(\[\]\)/, 'map must not populate the result panel before search');
assert.match(map, /Quick searches/);
assert.match(map, /visiblePage\.map/);
assert.match(map, /setSelected\(row\)/);

assert.match(cyclopedia, /itemsApi\.getPopular/);
assert.match(cyclopedia, /itemsApi\.getTrending/);
assert.match(cyclopedia, /cyclopedia\.discovery\.trendingLoot/);
assert.match(quests, /lg:grid-cols-\[minmax\(0,7fr\)_minmax\(16rem,3fr\)\]/);
assert.ok(quests.indexOf('const allTime') < quests.indexOf('const personal'), 'all-time shelf must own its entries first');

assert.match(navigation, /shortLabel: 'Planner'/);
assert.match(navigation, /shortLabel: 'Map'/);
assert.match(navigation, /lg:hidden/);
assert.match(navigation, /iconOnly: true/);

assert.match(cyclopedia, /resultBlocks\[1\]/, 'sticky boundary must use the second result block');
assert.match(cyclopedia, /setIsSearchPreparing\(true\)/);
assert.match(cyclopedia, /window\.clearTimeout\(compactTimerRef\.current\)/);

assert.match(notifications, /notificationApi\.list\(items\.length, 20\)/);
assert.match(adminUsers, /<table/);
assert.match(adminUsers, /getUsers\(0, 50/);
assert.match(adminUsers, /getUsers\(users\.length, 50/);
assert.match(members, /<MemberDetail/);
assert.match(members, /member\.linked_email/);

for (const field of ['effective_min_level', 'suggested_level', 'level_fit', 'danger', 'raw_creature_exp']) {
  assert.ok(planner.includes(field), `planner recommendation cards must expose ${field}`);
}

console.log('Public beta patch 1 checks passed: Planner, map, shelves, navigation, sticky transition, pagination, admin table, and member detail contracts are present.');
