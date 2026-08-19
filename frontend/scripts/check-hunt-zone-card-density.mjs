import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexCss = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8');
const cardsCss = fs.readFileSync(path.join(root, 'src/styles/hunt-zone-cards.css'), 'utf8');
const card = fs.readFileSync(path.join(root, 'src/components/HuntZoneCard.tsx'), 'utf8');
const cyclopedia = fs.readFileSync(path.join(root, 'src/pages/CreaturesPage.tsx'), 'utf8');
const planner = fs.readFileSync(path.join(root, 'src/pages/HuntRecommendationsPage.tsx'), 'utf8');

const checks = [
  [indexCss.includes("@import './styles/hunt-zone-cards.css';"), 'shared Hunt Zone styles must be loaded globally'],
  [cardsCss.includes('[data-hunt-zone-card]') && !cardsCss.includes(':has('), 'Hunt Zone layout must use an explicit component contract, not broad relational selectors'],
  [card.includes('min-h-[21rem]') && card.includes('flex-1 flex-col'), 'shared Hunt Zone cards need a stable aligned height and vertical layout'],
  [card.includes('LocalizedMapPreview') && card.includes('absolute inset-0'), 'localized maps must fill the card background'],
  [cyclopedia.includes('<HuntZoneCard') && cyclopedia.includes('xl:grid-cols-4'), 'Cyclopedia must reuse the shared card in its responsive grid'],
  [planner.includes('<HuntZoneCard') && planner.includes('xl:grid-cols-3'), 'Planner recommendations must reuse the shared aligned card grid'],
  [planner.includes('col-span-full'), 'Planner status and loading rows must span the recommendation grid'],
];

const failed = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failed.length) {
  console.error('Hunt Zone card density checks failed:');
  for (const message of failed) console.error(`- ${message}`);
  process.exit(1);
}

console.log('Hunt Zone card density checks passed: Cyclopedia and Planner share aligned localized-map cards.');
