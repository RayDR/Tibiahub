import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexCss = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8');
const codexCss = fs.readFileSync(path.join(root, 'src/styles/quest-codex.css'), 'utf8');
const detail = fs.readFileSync(path.join(root, 'src/pages/QuestDetailPage.tsx'), 'utf8');
const library = fs.readFileSync(path.join(root, 'src/components/QuestLibraryShelves.tsx'), 'utf8');

const checks = [
  [indexCss.includes("@import './styles/quest-codex.css';"), 'Quest codex stylesheet must be loaded'],
  [detail.includes('quest-codex relative'), 'Quest Detail must opt into the codex treatment'],
  [detail.includes('quest-codex__binding'), 'Quest Detail must render the book binding'],
  [detail.includes('quest-codex__spread'), 'Quest Detail must retain the open-book spread layout'],
  [codexCss.includes('@media (min-width: 1024px)'), 'Quest codex must provide a desktop open-book treatment'],
  [codexCss.includes('var(--surface-inverse)'), 'Quest parchment must derive from theme tokens'],
  [library.includes('activeBrowseRef.current?.abort()'), 'Quest Library must cancel stale browse requests'],
  [library.includes('controller.signal'), 'Quest Library browse requests must use AbortSignal'],
  [library.includes('scrollIntoView'), 'Selecting a Quest must bring its preview into view'],
  [library.includes("hasMore ? `${quests.length}+` : quests.length"), 'Search result count must distinguish partial pagination'],
];

const failed = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failed.length) {
  console.error('Quest product polish checks failed:');
  for (const message of failed) console.error(`- ${message}`);
  process.exit(1);
}

console.log('Quest product polish checks passed: codex detail and Quest Library interaction guards are wired.');
