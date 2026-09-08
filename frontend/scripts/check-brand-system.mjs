import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const sourceRoot = join(frontendRoot, 'src');
const brandSystem = readFileSync(join(frontendRoot, 'BRAND_SYSTEM.md'), 'utf8');
const designSystem = readFileSync(join(frontendRoot, 'DESIGN_SYSTEM.md'), 'utf8');
const designCss = readFileSync(join(sourceRoot, 'styles', 'design-system.css'), 'utf8');
const themes = readFileSync(join(sourceRoot, 'styles', 'themes.css'), 'utf8');

const failures = [];
const warnings = [];

for (const section of [
  '## Authority',
  '## Brand position',
  '## Canonical identity vs. themes',
  '## Typography',
  '## Color',
  '## Iconography',
  '## Game media',
  '## Cyclopedia composition',
  '## Maps and coordinates',
  '## Navigation and shells',
  '## Motion',
  '## Implementation rules',
  '## Definition of done for visual work',
]) {
  if (!brandSystem.includes(section)) failures.push(`BRAND_SYSTEM.md: missing required section ${section}`);
}

for (const contract of [
  "--font-body: 'Inter'",
  "--font-heading: 'Cinzel'",
  '--font-mono:',
  '--radius-sm:',
  '--radius-md:',
  '--radius-lg:',
  '--radius-xl:',
  '--radius-2xl:',
  '--duration-fast:',
  '--duration-base:',
]) {
  if (!designCss.includes(contract)) failures.push(`styles/design-system.css: missing brand foundation contract ${contract}`);
}

// Current develop uses tibia-stone as the canonical/default appearance. The
// root token block and explicit tibia-stone selector intentionally share it.
if (!themes.includes(':root,') || !themes.includes('[data-theme="tibia-stone"]')) {
  failures.push('styles/themes.css: canonical tibia-stone/root theme contract is missing');
}
if (!designSystem.includes('BRAND_SYSTEM.md')) failures.push('DESIGN_SYSTEM.md: must reference BRAND_SYSTEM.md as the higher-level visual contract');

const files = [];
const walk = (directory) => {
  for (const name of readdirSync(directory)) {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) walk(path);
    else files.push(path);
  }
};
walk(sourceRoot);

const sourceFiles = files.filter((path) => ['.ts', '.tsx', '.js', '.jsx'].includes(extname(path)));

// Exact Font Awesome debt found on the current develop baseline. Any new usage
// outside this list fails validation. Stale entries also fail so this list can
// only shrink as migration work lands.
const fontAwesomeBaseline = new Set([
  'src/components/LanguageSwitcher.tsx',
  'src/components/ui/AppInput.tsx',
  'src/components/ui/PageHeader.tsx',
  'src/pages/CreaturesPage.tsx',
  'src/pages/HuntRecommendationsPage.tsx',
  'src/pages/RafflePublicPage.tsx',
  'src/pages/guild/Raffle.tsx',
]);

for (const path of sourceFiles) {
  const source = readFileSync(path, 'utf8');
  const rel = relative(frontendRoot, path).replaceAll('\\', '/');
  const usesFontAwesome = /from ['"]@fortawesome\//.test(source);

  if (usesFontAwesome && !fontAwesomeBaseline.has(rel)) {
    failures.push(`${rel}: Font Awesome usage is outside the legacy baseline; use Lucide for interface icons or TibiaHub SVG domain icons`);
  }
  if (usesFontAwesome && fontAwesomeBaseline.has(rel)) warnings.push(`${rel}: existing Font Awesome migration debt`);
}

for (const rel of fontAwesomeBaseline) {
  const path = join(frontendRoot, rel);
  try {
    const source = readFileSync(path, 'utf8');
    if (!/from ['"]@fortawesome\//.test(source)) failures.push(`${rel}: remove stale Font Awesome baseline entry; this file no longer imports Font Awesome`);
  } catch {
    failures.push(`${rel}: remove stale Font Awesome baseline entry; file no longer exists`);
  }
}

for (const path of sourceFiles.filter((path) => relative(sourceRoot, path).replaceAll('\\', '/').startsWith('components/icons/'))) {
  const source = readFileSync(path, 'utf8');
  const rel = relative(frontendRoot, path).replaceAll('\\', '/');
  const literalSvgPaint = /(?:fill|stroke)=["'](?!none\b|currentColor\b|inherit\b|transparent\b|url\()[^"']+["']/g;
  for (const match of source.matchAll(literalSvgPaint)) failures.push(`${rel}: domain SVG uses non-semantic paint ${match[0]}`);
}

if (warnings.length) {
  console.warn(`Brand-system warnings (${warnings.length}):`);
  for (const warning of warnings) console.warn(`- ${warning}`);
}

if (failures.length) {
  console.error(`Brand-system validation failed (${failures.length} issue${failures.length === 1 ? '' : 's'}):`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Brand-system validation passed: ${sourceFiles.length} source files checked, tibia-stone canonical identity present, typography/shape/motion contracts present, icon policy enforced.`);
