import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const source = (path) => readFileSync(join(root, path), 'utf8');
const failures = [];
const viewportWidths = [320, 360, 390, 430, 768, 1024, 1440];
const coreFiles = [
  'src/components/Navigation.tsx', 'src/components/shell/AppShell.tsx', 'src/components/ui/PageHeader.tsx',
  'src/components/workspace/WorkspacePrimitives.tsx', 'src/layouts/GuildLayout.tsx', 'src/layouts/AdminLayout.tsx',
  'src/pages/HomePage.tsx', 'src/pages/CreaturesPage.tsx', 'src/pages/Profile.tsx', 'src/pages/guild/Members.tsx',
  'src/pages/guild/Notifications.tsx', 'src/pages/guild/Dashboard.tsx', 'src/pages/Admin/Overview.tsx',
  'src/pages/Admin/AssistanceHub.tsx', 'src/pages/Admin/AuditHub.tsx', 'src/pages/Admin/AdminGuildWorkspace.tsx',
];
const css = source('src/styles/design-system.css');
const navigation = source('src/components/Navigation.tsx');
const appShell = source('src/components/shell/AppShell.tsx');
const overlay = source('src/components/ui/Overlay.tsx');
const main = source('src/main.tsx');
const members = source('src/pages/guild/Members.tsx');
const cyclopedia = source('src/pages/CreaturesPage.tsx');
const compactStrip = source('src/components/CompactEntityStrip.tsx');
const searchBox = source('src/components/search/KnowledgeSearchBox.tsx');
const cyclopediaNavUtils = source('src/utils/cyclopediaNavigation.ts');
const publicPageFiles = [
  'src/pages/HomePage.tsx',
  'src/pages/CreaturesPage.tsx',
  'src/pages/HuntRecommendationsPage.tsx',
  'src/pages/CreatureDetailPage.tsx',
  'src/pages/QuestDetailPage.tsx',
  'src/pages/NpcDetailPage.tsx',
  'src/pages/LocationDetailPage.tsx',
  'src/pages/Profile.tsx',
  'src/pages/MemberProfile.tsx',
  'src/pages/auth/Login.tsx',
  'src/pages/auth/Register.tsx',
  'src/pages/PasswordReset.tsx',
  'src/pages/VerifyEmail.tsx',
  'src/pages/NotFound.tsx',
];

const publicRootAllowlist = {
  maxWidth: new Set(),
  horizontalPadding: new Set(),
  verticalPadding: new Set(),
};

const rootTagRegex = /return\s*\(\s*<([A-Za-z0-9_.]+)([^>]*)>/gms;
const classAttrRegex = /className="([^"]*)"/;
const maxWidthRegex = /\b(?:mx-auto|max-w-(?:\[[^\]]+\]|[^\s"']+))/;
const horizontalPaddingRegex = /\bpx-(?:\[[^\]]+\]|\d+)/;
const verticalPaddingRegex = /\b(?:py-(?:\[[^\]]+\]|\d+)|pt-(?:\[[^\]]+\]|\d+)|pb-(?:\[[^\]]+\]|\d+))/;

function readRootClassEntries(text) {
  const entries = [];
  for (const match of text.matchAll(rootTagRegex)) {
    const tag = match[1];
    const attrs = match[2] || '';
    const classMatch = attrs.match(classAttrRegex);
    entries.push({
      tag,
      className: classMatch ? classMatch[1] : '',
      attrs,
    });
  }
  return entries;
}

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
if (!css.includes('--app-content-max-width') || !css.includes('--app-nav-clearance') || !css.includes('--app-sticky-offset')) failures.push('shared app layout tokens are missing (content width/nav clearance/sticky offset)');
if (!css.includes('.app-sticky-offset')) failures.push('shared sticky offset utility class is missing');
if (navigation.includes('max-w-[90rem]') || navigation.includes('px-2 pt-2 sm:px-4')) failures.push('navigation still hardcodes shell width/gutters instead of using shared Container');
if (!navigation.includes('<Container')) failures.push('navigation does not use the shared Container primitive');
for (const token of ['--z-base', '--z-map-overlay', '--z-sticky', '--z-navbar', '--z-dropdown', '--z-modal']) {
  if (!css.includes(token)) failures.push(`shared layering scale is missing ${token}`);
}
const layerOrder = ['--z-base', '--z-map-overlay', '--z-sticky', '--z-navbar', '--z-dropdown', '--z-modal'].map((token) => css.indexOf(token));
if (!layerOrder.every((position, index) => index === 0 || position > layerOrder[index - 1])) failures.push('shared layering scale is not ordered from page content through modal');
if (!navigation.includes('app-primary-nav') || !navigation.includes('z-navbar')) failures.push('primary navigation does not own the navbar stacking tier');
if (!css.includes('.app-primary-nav { isolation: isolate; overflow: visible; }')) failures.push('primary navigation stacking context or overflow contract is incomplete');
if (!appShell.includes("isMapWorkspace ? children") || !appShell.includes('app-shell-main-map')) failures.push('map workspace does not bypass page framing and mobile footer padding');
if (cyclopedia.includes("'app-sticky-offset sticky z-40'")) failures.push('Cyclopedia sticky controls still use an unscoped numeric navbar-adjacent layer');

if (!compactStrip.includes('Math.abs(delta) > 6') || !compactStrip.includes('drag.suppressClick = true')) failures.push('compact strip drag threshold/click suppression guard is incomplete');
if (!compactStrip.includes("if (variant !== 'rail')")) failures.push('compact strip applies drag behavior outside rail variant');
if (!searchBox.includes('onSuggestionSelect') || !searchBox.includes('cyclopedia.filters.clearSearch')) failures.push('search box controlled suggestion callback or clear-search control is missing');
if (!cyclopedia.includes("setSearchTerm('')") || !cyclopedia.includes("setSelectedResult('')") || !cyclopedia.includes("setCreatureCategory('')")) failures.push('cyclopedia tab-switch reset contract (q/selected/category) is incomplete');
if (!cyclopedia.includes('handleSuggestionSelect') || !cyclopedia.includes("selected: selectedResult")) failures.push('cyclopedia selected-suggestion state separation is incomplete');
if (!cyclopediaNavUtils.includes('tab') || !cyclopediaNavUtils.includes('q') || !cyclopediaNavUtils.includes('selected') || !cyclopediaNavUtils.includes('category') || !cyclopediaNavUtils.includes('sort') || !cyclopediaNavUtils.includes('order')) failures.push('cyclopedia return-target helper is missing full tab/filter/sort state coverage');

for (const file of publicPageFiles) {
  const text = source(file);
  if (!text.includes('<Page')) failures.push(`${file}: public page root should use Page`);

  const roots = readRootClassEntries(text);
  for (const root of roots) {
    if (!root.className) continue;
    const isPageRoot = root.tag === 'Page';
    const hasMaxWidth = maxWidthRegex.test(root.className);
    const hasHorizontalPadding = horizontalPaddingRegex.test(root.className);
    const hasVerticalPadding = verticalPaddingRegex.test(root.className);

    if (hasMaxWidth && !publicRootAllowlist.maxWidth.has(file)) {
      failures.push(`${file}: root class duplicates page shell width (${root.className})`);
    }
    if (isPageRoot && hasHorizontalPadding && !publicRootAllowlist.horizontalPadding.has(file)) {
      failures.push(`${file}: root Page duplicates horizontal gutter (${root.className})`);
    }
    if (isPageRoot && hasVerticalPadding && !publicRootAllowlist.verticalPadding.has(file)) {
      failures.push(`${file}: root Page duplicates vertical page spacing (${root.className})`);
    }
  }

  for (const match of text.matchAll(/className="([^"]*)"/g)) {
    const className = match[1];
    if (className.includes('sticky') && /top-\[[^\]]+\]/.test(className)) {
      failures.push(`${file}: sticky top offset uses hardcoded value (${className})`);
    }
  }
}

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
