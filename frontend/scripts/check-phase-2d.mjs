import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const readRoot = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');

const activePages = [
  'src/pages/guild/Dashboard.tsx', 'src/pages/guild/Members.tsx',
  'src/pages/guild/Announcements.tsx', 'src/pages/guild/Events.tsx',
  'src/pages/guild/Leadership.tsx', 'src/pages/guild/LeadershipRecruitment.tsx',
  'src/pages/guild/LeadershipApplicationDetail.tsx', 'src/pages/guild/GuildHuntPlanner.tsx',
  'src/pages/guild/RafflesWorkspace.tsx', 'src/pages/guild/Raffle.tsx',
  'src/pages/guild/Notifications.tsx', 'src/pages/Admin/Overview.tsx',
  'src/pages/Admin/GuildDirectory.tsx', 'src/pages/Admin/AssistanceHub.tsx',
  'src/pages/Admin/RaffleAssistance.tsx', 'src/pages/Admin/AdminGuildWorkspace.tsx',
  'src/pages/Admin/Users.tsx', 'src/pages/Admin/GlobalActivities.tsx',
  'src/pages/Admin/BestiaryManagement.tsx', 'src/pages/Admin/DataTools.tsx',
  'src/pages/Admin/FullSyncDashboard.tsx', 'src/pages/Admin/SyncPhaseCard.tsx',
  'src/pages/Admin/SyncErrorDialog.tsx',
  'src/pages/Admin/KnowledgeOperations.tsx', 'src/pages/Admin/KnowledgeRelationshipReview.tsx',
  'src/pages/Admin/AuditHub.tsx', 'src/pages/Admin/MaintenanceControl.tsx',
  'src/pages/Admin/Maintenance.tsx', 'src/pages/Admin/Settings.tsx',
  'src/pages/Admin/ThemePlayground.tsx',
  'src/pages/guild/AutomaticRaffleOperations.tsx',
];

const [localeSource, dataDisplay, users, emailService, ...sources] = await Promise.all([
  read('src/utils/locale.ts'),
  read('src/components/ui/DataDisplay.tsx'),
  read('src/pages/Admin/Users.tsx'),
  readRoot('backend/app/services/email_service.py'),
  ...activePages.map(read),
]);

assert.match(dataDisplay, /t\('pagination\.status'/, 'shared pagination status must use i18n');
assert.match(dataDisplay, /t\('pagination\.previous'/, 'shared previous action must use i18n');
assert.match(dataDisplay, /t\('pagination\.next'/, 'shared next action must use i18n');
assert.doesNotMatch(users, /adminEmailApi\.(?:verify|reset)\([^\n]+,\s*['"]en['"]\)/, 'Admin email actions must not force English');
assert.match(users, /supportedLanguage\(i18n\.resolvedLanguage \|\| i18n\.language\)/);
assert.match(emailService, /locale\.casefold\(\)\.startswith\("es"\)/, 'backend must provide Spanish email content');

const forbiddenCopy = [
  'Bestiary Management', 'Search creature...', 'System Settings',
  'Loading system settings...', 'Checking external APIs...', 'Create Event',
  'Unable to load announcements', 'Load more', 'User pagination',
];
for (const [index, source] of sources.entries()) {
  for (const copy of forbiddenCopy) {
    assert.equal(source.includes(`>${copy}<`) || source.includes(`title="${copy}"`) || source.includes(`placeholder="${copy}"`), false,
      `${activePages[index]} contains migrated hardcoded UI copy: ${copy}`);
  }
  assert.doesNotMatch(source, /\.toLocale(?:String|DateString|TimeString)\(\s*\)/,
    `${activePages[index]} relies on the browser locale for visible formatting`);
}

const transpiled = ts.transpileModule(localeSource, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const locale = await import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`);
assert.equal(locale.appLocale('en'), 'en-US');
assert.equal(locale.appLocale('en-GB'), 'en-US');
assert.equal(locale.appLocale('es'), 'es-MX');
assert.equal(locale.appLocale('es-ES'), 'es-MX');
assert.equal(locale.supportedLanguage('es-MX'), 'es');
assert.equal(locale.supportedLanguage('fr'), 'en');
const sample = new Date('2026-09-01T17:30:00Z');
assert.match(locale.formatDate(sample, 'en', { timeZone: 'UTC' }), /9\/1\/2026/);
assert.match(locale.formatDate(sample, 'es', { timeZone: 'UTC' }), /1\/9\/2026/);
assert.equal(locale.formatNumber(1234.5, 'en'), '1,234.5');
assert.equal(locale.formatNumber(1234.5, 'es'), '1,234.5');

console.log(`Phase 2D checks passed: ${activePages.length} active routes use selected-locale presentation and migrated copy guards.`);
