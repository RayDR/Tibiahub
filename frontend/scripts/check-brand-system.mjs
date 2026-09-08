import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const sourceRoot = join(frontendRoot, 'src');
const brandSystemPath = join(frontendRoot, 'BRAND_SYSTEM.md');
const designSystemPath = join(frontendRoot, 'DESIGN_SYSTEM.md');
const designCssPath = join(sourceRoot, 'styles', 'design-system.css');
const themesPath = join(sourceRoot, 'styles', 'themes.css');

const failures = [];
const warnings = [];

const brandSystem = readFileSync(brandSystemPath, 'utf8');
const designSystem = readFileSync(designSystemPath, 'utf8');
const designCss = readFileSync(designCssPath, 'utf8');
const themes = readFileSync(themesPath, 'utf8');

const requiredBrandSections = [
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
];

for (const section of requiredBrandSections) {
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

if (!themes.includes('[data-theme="default"]')) failures.push('styles/themes.css: canonical default theme is missing');

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

// Existing Font Awesome usage is migration debt. Keep the complete current
// baseline explicit so the validator prevents the debt from spreading while
// allowing the migration to happen incrementally.
const fontAwesomeBaseline = new Set([
  'src/components/LanguageSwitcher.tsx',
  'src/components/Navigation.tsx',
  'src/components/ui/AppInput.tsx',
  'src/components/ui/PageHeader.tsx',
  'src/config/cyclopediaSections.ts',
  'src/pages/Admin/APIMonitor.tsx',
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
    failures.push(`${rel}: new Font Awesome usage is forbidden; use Lucide for interface icons or TibiaHub SVG domain icons`);
  }

  if (usesFontAwesome && fontAwesomeBaseline.has(rel)) {
    warnings.push(`${rel}: existing Font Awesome migration debt`);
  }
}

// Keep the baseline honest. When a legacy import is removed, this intentionally
// fails until the obsolete allowlist entry is deleted too. The allowlist can
// only shrink; stale entries cannot silently remain forever.
for (const rel of fontAwesomeBaseline) {
  const path = join(frontendRoot, rel);
  try {
    const source = readFileSync(path, 'utf8');
    if (!/from ['"]@fortawesome\//.test(source)) {
      failures.push(`${rel}: remove stale Font Awesome baseline entry; this file no longer imports Font Awesome`);
    }
  } catch {
    failures.push(`${rel}: remove stale Font Awesome baseline entry; file no longer exists`);
  }
}

// Domain SVGs are theme-safe: literal fill/stroke colors are not allowed in
// TibiaHub-owned icon components. currentColor, none, inherited values, and
// referenced paint servers remain allowed.
for (const path of sourceFiles.filter((path) => relative(sourceRoot, path).replaceAll('\\', '/').startsWith('components/icons/'))) {
  const source = readFileSync(path, 'utf8');
  const rel = relative(frontendRoot, path).replaceAll('\\', '/');
  const literalSvgPaint = /(?:fill|stroke)=["'](?!none\b|currentColor\b|inherit\b|transparent\b|url\()[^"']+["']/g;
  for (const match of source.matchAll(literalSvgPaint)) {
    failures.push(`${rel}: domain SVG uses non-semantic paint ${match[0]}`);
  }
}

// Keep the documented hierarchy visible in the technical design-system doc so
// contributors discover the product-level contract from either entry point.
if (!designSystem.includes('BRAND_SYSTEM.md')) {
  failures.push('DESIGN_SYSTEM.md: must reference BRAND_SYSTEM.md as the higher-level visual contract');
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

console.log(`Brand-system validation passed: ${sourceFiles.length} source files checked, canonical identity present, typography/shape/motion contracts present, icon policy enforced.`);
