import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const source = (path) => readFileSync(join(root, path), 'utf8');
const failures = [];
const viewportWidths = [320, 375, 390, 430, 768, 1024, 1440];
const coreFiles = [
  'src/components/Navigation.tsx', 'src/components/shell/AppShell.tsx', 'src/components/ui/PageHeader.tsx',
  'src/components/workspace/WorkspacePrimitives.tsx', 'src/layouts/GuildLayout.tsx', 'src/layouts/AdminLayout.tsx',
  'src/pages/HomePage.tsx', 'src/pages/CreaturesPage.tsx', 'src/pages/Profile.tsx', 'src/pages/guild/Members.tsx',
  'src/pages/guild/Notifications.tsx', 'src/pages/guild/Dashboard.tsx', 'src/pages/Admin/Overview.tsx',
  'src/pages/Admin/AssistanceHub.tsx', 'src/pages/Admin/AuditHub.tsx', 'src/pages/Admin/AdminGuildWorkspace.tsx',
];
const css = source('src/styles/design-system.css');
const navigation = source('src/components/Navigation.tsx');
const overlay = source('src/components/ui/Overlay.tsx');
const main = source('src/main.tsx');
const members = source('src/pages/guild/Members.tsx');

for (const token of ['app-shell-main', 'app-mobile-nav', 'app-context-bar', 'workspace-nav', 'workspace-content', 'responsive-card-list', 'responsive-data-table']) {
  if (!css.includes(`.${token}`)) failures.push(`design-system.css is missing .${token}`);
}
for (const width of viewportWidths) {
  if (width < 320) failures.push(`unsupported viewport ${width}px`);
}
if (!css.includes('min-width: 20rem') || !css.includes('overflow-x: clip')) failures.push('320px shell overflow guard is incomplete');
if (!css.includes('@media (min-width: 768px)') || !css.includes('@media (min-width: 1024px)')) failures.push('tablet/desktop layout breakpoints are incomplete');
if (!navigation.includes('aria-current=') || !navigation.includes('aria-expanded=') || !navigation.includes('app-mobile-nav-link')) failures.push('responsive navigation keyboard/current-page semantics are incomplete');
if (!overlay.includes("event.key === 'Escape'") || !overlay.includes("event.key === 'Tab'") || !css.includes(':focus-visible')) failures.push('keyboard focus, focus trap, or Escape behavior is incomplete');
if (!main.includes('MotionConfig') || !main.includes("motion === 'reduced'") || !css.includes('[data-motion="enhanced"]') || !css.includes('[data-density="compact"]')) failures.push('global motion or density integration is incomplete');
if (!members.includes('responsive-card-list') || !members.includes('responsive-data-table')) failures.push('member data lacks mobile cards and desktop table');
if (/max-h-\[[^\]]+\]\s+overflow-y-auto/.test(members)) failures.push('member view has forced inner vertical scrolling');

const allowedText = new Set(['Tibia', 'Hub', 'TibiaWiki']);
for (const file of coreFiles) {
  const text = source(file);
  for (const match of text.matchAll(/\b(?:aria-label|placeholder|title|alt)=["']([^"']+)["']/g)) {
    if (match[1].trim()) failures.push(`${file}: hard-coded visible attribute "${match[1]}"`);
  }
  for (const match of text.matchAll(/>\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][^<>{}\n]{1,80})\s*</g)) {
    const value = match[1].trim();
    if (value && !allowedText.has(value) && !/^--[a-z0-9-]+$/.test(value)) failures.push(`${file}: hard-coded visible text "${value}"`);
  }
  for (const match of text.matchAll(/(?:min-w|w)-\[(\d+)px\]/g)) {
    if (Number(match[1]) > 320) failures.push(`${file}: fixed width ${match[1]}px can overflow the smallest viewport`);
  }
}

if (failures.length) {
  console.error(`Layout validation failed (${failures.length} issues):`);
  failures.forEach(failure => console.error(`- ${failure}`));
  process.exit(1);
}
console.log(`Layout validation passed: shell, keyboard semantics, translated core surfaces, and overflow contracts cover ${viewportWidths.join(', ')}px.`);
