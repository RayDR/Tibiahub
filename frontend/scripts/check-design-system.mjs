import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const sourceRoot = join(frontendRoot, 'src');
const designSystemPath = join(sourceRoot, 'styles', 'design-system.css');
const designSystem = readFileSync(designSystemPath, 'utf8');
const themeSwitcher = readFileSync(join(sourceRoot, 'components', 'ThemeSwitcher.tsx'), 'utf8');
const failures = [];

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
const styleFiles = files.filter((path) => extname(path) === '.css' && path !== designSystemPath);
const paletteUtility = /(?:^|[^\w-])(?:text|bg|border|ring|from|via|to|shadow|placeholder|divide|decoration|outline|accent)-(?:slate|gray|zinc|neutral|stone|amber|yellow|orange|red|rose|green|emerald|teal|blue|sky|cyan|purple|violet|indigo|fuchsia|pink|white|black|tibia)(?:-|\/|\b)/g;
const literalColor = /#[\da-f]{3,8}\b|rgba?\(\s*\d|hsla?\(/gi;
const arbitraryColorVariable = /(?:text|bg|border|ring|from|via|to)-\[(?:color:)?var\(/g;

const reportMatches = (path, pattern, label) => {
  const text = readFileSync(path, 'utf8');
  const matches = [...text.matchAll(pattern)];
  for (const match of matches) {
    const line = text.slice(0, match.index).split('\n').length;
    failures.push(`${relative(frontendRoot, path)}:${line}: ${label}: ${match[0].trim()}`);
  }
};

for (const path of sourceFiles) {
  reportMatches(path, paletteUtility, 'non-semantic palette utility');
  reportMatches(path, literalColor, 'hardcoded color');
  reportMatches(path, arbitraryColorVariable, 'legacy arbitrary color token');
}
for (const path of styleFiles) reportMatches(path, literalColor, 'hardcoded stylesheet color');

const requiredThemeTokens = [
  'surface-base', 'surface', 'surface-raised', 'surface-hover', 'surface-active', 'surface-overlay', 'surface-inverse',
  'primary', 'primary-hover', 'primary-active', 'success', 'warning', 'danger', 'info', 'accent',
  'text-primary', 'text-secondary', 'text-muted', 'text-inverse', 'text-on-primary', 'border', 'border-strong', 'focus',
];
for (const theme of ['default', 'medieval', 'tibia-stone']) {
  const selector = theme === 'default' ? '[data-theme="default"]' : `[data-theme="${theme}"]`;
  const start = designSystem.indexOf(selector);
  const open = designSystem.indexOf('{', start);
  const close = designSystem.indexOf('}', open);
  const block = start >= 0 && open >= 0 && close >= 0 ? designSystem.slice(open, close) : '';
  for (const token of requiredThemeTokens) {
    if (!block.includes(`--ds-${token}:`)) failures.push(`styles/design-system.css: theme "${theme}" lacks --ds-${token}`);
  }
}

for (const primitive of ['ds-container', 'ds-page', 'ds-section', 'ds-panel', 'ds-card', 'ds-toolbar', 'ds-split-view', 'ds-sidebar', 'ds-scrollable-panel']) {
  if (!designSystem.includes(`.${primitive}`)) failures.push(`styles/design-system.css: missing layout primitive .${primitive}`);
}

for (const breakpoint of ['640px', '1024px']) {
  if (!designSystem.includes(`@media (min-width: ${breakpoint})`)) failures.push(`styles/design-system.css: missing responsive breakpoint ${breakpoint}`);
}
if (!designSystem.includes('@media (prefers-reduced-motion: reduce)')) failures.push('styles/design-system.css: missing reduced-motion behavior');
for (const theme of ['default', 'medieval', 'tibia-stone']) {
  if (!themeSwitcher.includes(`'${theme}'`)) failures.push(`components/ThemeSwitcher.tsx: missing theme "${theme}"`);
}
if (!themeSwitcher.includes("setAttribute('data-theme'")) failures.push('components/ThemeSwitcher.tsx: theme selection does not update data-theme');

if (failures.length) {
  console.error(`Design-system validation failed (${failures.length} issue${failures.length === 1 ? '' : 's'}):`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Design-system validation passed: ${sourceFiles.length} source files, ${styleFiles.length} stylesheets, 3 complete themes.`);
