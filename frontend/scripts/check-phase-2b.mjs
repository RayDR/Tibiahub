import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const [overlay, controls, styles, announcements, events, hunts, recruitment, dataTools, settings, bestiary, guildWorkspace, globalActivities, dashboard, overview] = await Promise.all([
  read('src/components/ui/Overlay.tsx'),
  read('src/components/ui/FormControls.tsx'),
  read('src/styles/design-system.css'),
  read('src/pages/guild/Announcements.tsx'),
  read('src/pages/guild/Events.tsx'),
  read('src/pages/guild/GuildHuntPlanner.tsx'),
  read('src/pages/guild/LeadershipRecruitment.tsx'),
  read('src/pages/Admin/DataTools.tsx'),
  read('src/pages/Admin/Settings.tsx'),
  read('src/pages/Admin/BestiaryManagement.tsx'),
  read('src/pages/Admin/AdminGuildWorkspace.tsx'),
  read('src/pages/Admin/GlobalActivities.tsx'),
  read('src/pages/guild/Dashboard.tsx'),
  read('src/pages/Admin/Overview.tsx'),
]);

assert.match(overlay, /createPortal/);
assert.match(overlay, /event\.key === 'Escape'/);
assert.match(overlay, /event\.key === 'Tab'/);
assert.match(overlay, /previousFocus\?\.focus\(\)/);
assert.match(overlay, /onCloseRef\.current\(\)/);
assert.match(controls, /htmlFor=\{controlId\}/);
assert.match(controls, /'aria-describedby': descriptionId/);
assert.match(controls, /'aria-invalid': Boolean\(error\)/);

for (const [name, source] of Object.entries({ announcements, events, hunts, recruitment })) {
  assert.match(source, /<Dialog\b/, `${name} must use the shared Dialog`);
  assert.match(source, /<DialogHeader\b/, `${name} must structure dialog headers`);
  assert.match(source, /<DialogBody\b/, `${name} must structure dialog bodies`);
  assert.match(source, /<DialogFooter\b/, `${name} must structure dialog actions`);
  assert.match(source, /<FormField\b/, `${name} must use associated shared fields`);
}
assert.match(settings, /<FormField\b/);
assert.match(settings, /<Input\b/);
assert.match(bestiary, /<Input\b/);
assert.match(bestiary, /<Select\b/);
for (const [name, source] of Object.entries({ announcements, events, recruitment })) {
  assert.doesNotMatch(source, /fixed inset-0[^\n]*z-modal/, `${name} still contains a hand-built modal`);
}
assert.match(announcements, /if \(creating\) return/);
assert.match(events, /if \(submitting\) return/);
assert.match(events, /if \(created\) onClose\(\)/);
assert.match(events, /submitError/);
assert.match(hunts, /if \(busy\) return/);
assert.match(recruitment, /if \(busy\) return/);
assert.match(recruitment, /if \(!busy\) onCancel\(\)/);
assert.match(bestiary, /if \(saving\) return/);
assert.match(bestiary, /adminBestiary\.states\.saveError/);

for (const [name, source] of Object.entries({ events, dataTools, settings, bestiary, guildWorkspace, globalActivities })) {
  assert.match(source, /<ErrorState\b/, `${name} needs an explicit request-error state`);
  assert.match(source, /Retry|common\.retry|actions\.retry/, `${name} needs a retry action`);
}
for (const [name, source] of Object.entries({ events, dataTools, bestiary, guildWorkspace, dashboard, overview })) {
  assert.match(source, /<DegradedState\b/, `${name} needs a partial/degraded state`);
}
assert.match(globalActivities, /<LoadingState\b/);
assert.match(globalActivities, /<EmptyState\b/);
assert.match(styles, /max-height: calc\(100dvh/);
assert.match(styles, /\.ds-dialog-body[^}]*overflow-y: auto/);
assert.match(styles, /\.ds-dialog-footer[^}]*flex-wrap: wrap/);

console.log('Phase 2B checks passed: shared dialog/form behavior, mutation guards, and explicit page states are present.');
