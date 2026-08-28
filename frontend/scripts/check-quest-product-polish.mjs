import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexCss = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8');
const codexCss = fs.readFileSync(path.join(root, 'src/styles/quest-codex.css'), 'utf8');
const detail = fs.readFileSync(path.join(root, 'src/pages/QuestDetailPage.tsx'), 'utf8');
const library = fs.readFileSync(path.join(root, 'src/components/QuestLibraryShelves.tsx'), 'utf8');
const preview = fs.readFileSync(path.join(root, 'src/components/quest/QuestPreviewDialog.tsx'), 'utf8');
const reference = fs.readFileSync(path.join(root, 'src/components/quest/QuestReference.tsx'), 'utf8');
const progress = fs.readFileSync(path.join(root, 'src/components/quest/QuestCompletionControl.tsx'), 'utf8');
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
  [codexCss.includes('quest-codex__mobile-sticky-title') && detail.includes('quest-codex__mobile-sticky-title'), 'Quest Detail must preserve mobile title context while scrolling'],
  [!codexCss.includes('.quest-codex a,') && !codexCss.includes('.quest-codex .app-button-secondary {'), 'Quest codex must not override shared app button colors'],
  [library.includes('activeBrowseRef.current?.abort()'), 'Quest Library must cancel stale browse requests'],
  [library.includes('controller.signal'), 'Quest Library browse requests must use AbortSignal'],
  [preview.includes('<Dialog') && library.includes('<QuestPreviewDialog'), 'Quest preview must use the accessible modal foundation'],
  [preview.includes('detail?.duration') && !preview.includes('previewCounts.locations'), 'Quest preview must show optional duration without a Locations count metric'],
  [preview.includes('mission-${mission.id}') && detail.includes('id={`mission-${mission.id}`}'), 'Quest preview mission index must deep-link to exact mission anchors'],
  [reference.includes('resolveLocalItem') && reference.includes('resolution_status === \'resolved\''), 'Quest item and quest references must resolve local exact knowledge only'],
  [detail.includes('<QuestReference') && detail.includes('<QuestCompletionControl'), 'Quest Detail must render rich references and completion tracking'],
  [progress.includes('sessionStorage') && progress.includes('questProgressApi'), 'Quest completion must support session and authenticated character persistence'],
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

console.log('Quest product polish checks passed: codex, previews, rich references, progress, and interaction guards are wired.');
