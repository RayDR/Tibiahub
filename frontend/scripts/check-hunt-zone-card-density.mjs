import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexCss = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8');
const cardsCss = fs.readFileSync(path.join(root, 'src/styles/hunt-zone-cards.css'), 'utf8');

const checks = [
  [indexCss.includes("@import './styles/hunt-zone-cards.css';"), 'compact Hunt Zone styles must be loaded globally'],
  [cardsCss.includes("[data-cyclopedia-result]:has(a[href^='/hunt-zones/'])"), 'Cyclopedia Hunt Zone cards must be isolated from other result cards'],
  [cardsCss.includes('grid-template-columns: repeat(4, minmax(0, 1fr));'), 'desktop layouts must support four compact Hunt Zone cards per row'],
  [cardsCss.includes("section:has(> article a[href^='/hunt-zones/'])"), 'Planner recommendations must use the compact Hunt Zone grid'],
  [cardsCss.includes("button:has(> img) > span"), 'Planner creature previews must collapse to compact avatar controls'],
  [cardsCss.includes('grid-column: 1 / -1;'), 'Planner status rows must span the recommendation grid'],
];

const failed = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failed.length) {
  console.error('Hunt Zone card density checks failed:');
  for (const message of failed) console.error(`- ${message}`);
  process.exit(1);
}

console.log('Hunt Zone card density checks passed: Cyclopedia and Planner use compact responsive grids.');
