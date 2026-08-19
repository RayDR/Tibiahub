import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

function assertIncludes(source, value, message) {
  if (!source.includes(value)) throw new Error(message);
}

function assertExcludes(source, value, message) {
  if (source.includes(value)) throw new Error(message);
}

const app = read('src/App.tsx');
const routeExperience = read('src/components/navigation/RouteExperience.tsx');
const requestCache = read('src/services/knowledgeRequestCache.ts');
const cyclopediaCache = read('src/services/cyclopediaCache.ts');
const imageFallback = read('src/components/ImageWithFallback.tsx');
const itemDetail = read('src/pages/ItemDetailPage.tsx');
const tabs = read('src/components/ui/AppTabs.tsx');
const api = read('src/services/api.ts');

assertIncludes(
  app,
  '<Routes location={location}>',
  'Routes must preserve the router tree across pathname changes.',
);
assertExcludes(
  app,
  'key={location.pathname}',
  'Do not force-remount the complete route tree on every pathname change.',
);
assertIncludes(
  app,
  '<RouteExperience />',
  'Global route checkpoint restoration must remain mounted.',
);

assertIncludes(
  routeExperience,
  "useNavigationType",
  'Scroll restoration must distinguish POP from new navigation.',
);
assertIncludes(
  routeExperience,
  "location.pathname === '/cyclopedia'",
  'Back-to-top must support Cyclopedia.',
);
assertIncludes(
  routeExperience,
  "location.pathname === '/planner'",
  'Back-to-top must support Planner.',
);
assertIncludes(
  routeExperience,
  "window.history.scrollRestoration = 'manual'",
  'Browser/native and application scroll restoration must not fight each other.',
);

assertIncludes(
  requestCache,
  'const value = await loader();',
  'Knowledge cache must store only successful resolved reads.',
);
assertIncludes(
  cyclopediaCache,
  'clearKnowledgeRequestCache();',
  'Server data-version changes must invalidate the public knowledge cache.',
);
assertIncludes(
  imageFallback,
  'failedMediaUrls',
  'Failed media URLs must be remembered for the SPA session.',
);

assertIncludes(
  itemDetail,
  "activity_type: 'view_item'",
  'Item detail views must feed the shared personal-history rail.',
);
assertIncludes(
  tabs,
  '<CyclopediaPersonalHistoryStrip mode={personalHistoryMode} />',
  'Loot and Hunt Zones must reuse the shared personal-history strip.',
);
assertIncludes(
  api,
  'Compatibility shim for the legacy second Loot rail',
  'Legacy duplicate Loot trend request must remain disabled until its callsite is removed.',
);
assertExcludes(
  api,
  "cachedGet<ItemSearchResult[]>('/items/trending'",
  'Cyclopedia must not perform the redundant Loot trending GET.',
);

console.log(
  'Cyclopedia shell polish checks passed: route state, cache reuse, media failure dedupe, personal history and Loot dedupe are wired.',
);
