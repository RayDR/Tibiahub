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

// Existing Font Awesome usage is migration debt. Keep this baseline explicit so
// the check prevents new imports without forcing an unrelated rewrite today.
const fontAwesomeBaseline = new Set([
  'src/config/cyclopediaSections.ts',
  'src/components/Navigation.tsx',
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

// Domain SVGs are theme-safe: literal fill/stroke colors are not allowed in
// TibiaHub-owned icon components. currentColor, none, and inherited values are fine.
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
