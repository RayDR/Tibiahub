import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const progress = read('src/components/quest/QuestCompletionControl.tsx');
const service = read('src/services/questProgress.ts');
const detail = read('src/pages/QuestDetailPage.tsx');

const checks = [
  [progress.includes('sessionStorage'), 'anonymous Quest progress must remain session-scoped'],
  [progress.includes("ownership_status === 'verified'"), 'authenticated Quest progress must expose only verified characters'],
  [progress.includes('primary_character_id'), 'primary character should be preferred when available'],
  [service.includes("'/quest-progress/") || service.includes('`/quest-progress/${'), 'Quest progress client must use the dedicated authenticated endpoint'],
  [detail.includes('<QuestCompletionControl'), 'Quest Detail must expose the completion control'],
];

const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error(`Quest progress checks failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}

console.log('Quest progress checks passed: session fallback and verified-character persistence are wired.');
