import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexCss = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8');
const codexCss = fs.readFileSync(path.join(root, 'src/styles/quest-codex.css'), 'utf8');
const detail = fs.readFileSync(path.join(root, 'src/pages/QuestDetailPage.tsx'), 'utf8');
const library = fs.readFileSync(path.join(root, 'src/components/QuestLibraryShelves.tsx'), 'utf8');
const preview = fs.readFileSync(path.join(root, 'src/components/quest/QuestPreviewDialog.tsx'), 'utf8');
const mapInsets = fs.readFileSync(path.join(root, 'src/components/quest/QuestMapInsets.tsx'), 'utf8');
const presentation = fs.readFileSync(path.join(root, 'src/utils/questPresentation.ts'), 'utf8');
const richLinks = fs.readFileSync(path.join(root, 'src/components/knowledge/RichEntityLink.tsx'), 'utf8');
const themes = fs.readFileSync(path.join(root, 'src/styles/themes.css'), 'utf8');

const checks = [
  [indexCss.includes("@import './styles/quest-codex.css';"), 'Quest codex stylesheet must be loaded'],
  [detail.includes('quest-codex relative'), 'Quest Detail must opt into the codex treatment'],
  [detail.includes('quest-codex__binding'), 'Quest Detail must render the book binding'],
  [detail.includes('quest-codex__spread'), 'Quest Detail must retain the open-book spread layout'],
  [codexCss.includes('@media (min-width: 1024px)'), 'Quest codex must provide a desktop open-book treatment'],
  [codexCss.includes('var(--quest-surface)') && themes.includes('--quest-surface:'), 'Quest codex must derive from the theme material contract'],
  [codexCss.includes('quest-unroll') && codexCss.includes('[data-motion="system"]') && codexCss.includes('[data-motion="enhanced"]'), 'Quest entrance motion must honor appearance modes'],
  [library.includes('activeBrowseRef.current?.abort()'), 'Quest Library must cancel stale browse requests'],
  [library.includes('controller.signal'), 'Quest Library browse requests must use AbortSignal'],
  [preview.includes('<Dialog') && library.includes('<QuestPreviewDialog'), 'Quest preview must use the accessible modal foundation'],
  [presentation.includes('hasDetailedQuestData') && presentation.includes('supplied_fields'), 'Quest detail availability must use deterministic structured evidence'],
  [mapInsets.includes('spatialApi.forEntity') && mapInsets.includes('filter(trusted)'), 'Quest map insets must use trusted canonical spatial evidence'],
  [richLinks.includes("resolution_status") === false && detail.includes("resolution_status === 'resolved'"), 'Rich entity links must only receive exactly resolved relationships'],
  [library.includes("const countIsPartial = Boolean(query && hasMore);"), 'Search result count must mark partial pagination'],
];

const failed = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failed.length) {
  console.error('Quest product polish checks failed:');
  for (const message of failed) console.error(`- ${message}`);
  process.exit(1);
}

console.log('Quest product polish checks passed: codex detail and Quest Library interaction guards are wired.');
