import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const page = read('src/pages/CreaturesPage.tsx');
const library = read('src/components/QuestLibraryShelves.tsx');
const client = read('src/services/questBrowser.ts');

const checks = [
  [page.includes("mode === 'quests' ? (\n        <QuestLibraryShelves"), 'Quest Library must render for the quests tab regardless of search text'],
  [!page.includes('quests.map((quest, index)'), 'legacy oversized quest result cards must be removed'],
  [library.includes('access_only: accessOnly'), 'Access Quest filtering must use the canonical browser'],
  [library.includes("sort_by: sortBy"), 'quest sorting must be server-backed'],
  [library.includes('IntersectionObserver'), 'quest library must auto-paginate'],
  [library.includes('is_access_quest'), 'quest books must use explicit access evidence'],
  [client.includes("'/quests/browse'"), 'quest browser client must use the fixed browse endpoint'],
  [client.includes("'/quests/facets'"), 'quest browser client must load canonical facets'],
];

const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error(`Quest Library checks failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}

console.log('Quest Library checks passed: canonical browse, compact books, Access filter, sorting, and infinite scrolling are wired.');
