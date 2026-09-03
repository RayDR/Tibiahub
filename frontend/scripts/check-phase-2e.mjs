import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';

const source = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFile(source(path), 'utf8');

const removedModules = [
  'src/pages/guild/GuildEvents.tsx',
  'src/pages/guild/HuntCatalog.tsx',
  'src/pages/guild/Recruitment.tsx',
  'src/pages/Admin/GuildManagementDashboard.tsx',
  'src/pages/Admin/GuildView.tsx',
  'src/pages/Admin/APIMonitor.tsx',
  'src/pages/Admin/DatabaseSync.tsx',
];

await Promise.all(removedModules.map(async (path) => {
  await assert.rejects(access(source(path)), undefined, `${path} must remain removed`);
}));

const [
  app,
  adminLayout,
  guildLayout,
  adminGuildWorkspace,
  announcements,
  guildService,
  guildManagementService,
  huntCatalogService,
] = await Promise.all([
  read('src/App.tsx'),
  read('src/layouts/AdminLayout.tsx'),
  read('src/layouts/GuildLayout.tsx'),
  read('src/pages/Admin/AdminGuildWorkspace.tsx'),
  read('src/pages/guild/Announcements.tsx'),
  read('src/services/guild.ts'),
  read('src/services/guildManagement.ts'),
  read('src/services/huntCatalog.ts'),
]);

for (const component of [
  'GuildEvents',
  'HuntCatalog',
  'GuildManagementDashboard',
  'GuildView',
  'APIMonitor',
  'DatabaseSync',
]) {
  assert.doesNotMatch(app, new RegExp(`import\\s+${component}\\b`));
}

const canonicalRoutes = [
  /path="events" element={<Events \/>}/,
  /path="leadership\/recruitment"[\s\S]{0,180}<LeadershipRecruitment \/>/,
  /path="hunts" element={<GuildHuntPlanner \/>}/,
  /path="raffles" element={<RafflesWorkspace \/>}/,
  /path="raffles\/manage" element={<RaffleManagementPage \/>}/,
  /path="guilds" element={<GuildDirectory \/>}/,
  /path="users" element={<AdminUsers \/>}/,
  /path="data-tools" element={<DataTools \/>}/,
  /path="sync"[\s\S]{0,100}initialTab="admin-sync"/,
];
canonicalRoutes.forEach((pattern) => assert.match(app, pattern));

const redirects = [
  [/path="recruitment"[\s\S]{0,140}Navigate to="\/guild\/leadership\/recruitment" replace/, 'Guild recruitment'],
  [/path="raffle"[\s\S]{0,140}Navigate to="\/guild\/raffles\?section=history" replace/, 'Guild raffle'],
  [/path="automatic-raffles"[\s\S]{0,100}Navigate to="\/guild\/raffles" replace/, 'Automatic raffles'],
  [/path="api-monitor"[\s\S]{0,100}Navigate to="\/admin\/data-tools" replace/, 'API monitor'],
  [/path="database-sync"[\s\S]{0,100}Navigate to="\/admin\/sync" replace/, 'Database Sync'],
  [/path="management"[\s\S]{0,100}Navigate to="\/admin\/guilds" replace/, 'Admin management'],
  [/path="guild-view"[\s\S]{0,100}Navigate to="\/admin\/guilds" replace/, 'Admin Guild View'],
];
redirects.forEach(([pattern, label]) => assert.match(app, pattern, `${label} compatibility redirect is required`));

assert.doesNotMatch(`${adminLayout}\n${guildLayout}\n${adminGuildWorkspace}`, /to=["'{`]\/admin\/(?:management|guild-view)/);
assert.doesNotMatch(`${adminLayout}\n${guildLayout}`, /to=["'{`]\/(?:guild\/recruitment|guild\/raffle|guild\/automatic-raffles|admin\/api-monitor|admin\/database-sync)/);
assert.match(adminGuildWorkspace, /to="\/admin\/users"/);

assert.match(announcements, /guildApi\.deleteAnnouncement\(announcement\.id\)/);
assert.match(announcements, /confirmation\.confirm\(/);
assert.match(guildService, /deleteAnnouncement:[\s\S]{0,180}api\.delete\(`\/guild\/announcements\/\$\{announcementId\}`\)/);
assert.doesNotMatch(guildService, /createEvent:|attendEvent:|getRecruitments|reportRecruitment|export interface Recruitment/);

assert.doesNotMatch(guildManagementService, /getGuilds:|deleteUser:|updateUserCharacter:|syncGuild:/);

// The canonical Hunt Catalog contract is retained for the future Hunt/Map domain phase,
// but no legacy UI currently imports or routes it.
assert.match(huntCatalogService, /getHunts:/);
assert.match(huntCatalogService, /createHunt:/);
assert.match(huntCatalogService, /updateHunt:/);
assert.match(huntCatalogService, /deleteHunt:/);

console.log('Phase 2E checks passed: canonical routes, safe redirects, removed legacy modules, and migrated announcement deletion are verified.');
