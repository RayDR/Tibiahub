import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const sourceRoot = join(frontendRoot, 'src');
const designSystemPath = join(sourceRoot, 'styles', 'design-system.css');
const themesPath = join(sourceRoot, 'styles', 'themes.css');
const designSystem = readFileSync(designSystemPath, 'utf8');
const themesSource = readFileSync(themesPath, 'utf8');
const appearanceSource = readFileSync(join(sourceRoot, 'context', 'AppearanceContext.tsx'), 'utf8');
const themeSwitcher = readFileSync(join(sourceRoot, 'components', 'ThemeSwitcher.tsx'), 'utf8');
const failures = [];

const themeIds = ['default', 'medieval', 'tibia-stone', 'midnight-arcana', 'blood-moon', 'high-contrast'];
const requiredThemeTokens = [
  'surface-base', 'surface', 'surface-raised', 'surface-hover', 'surface-active', 'surface-overlay', 'surface-inverse',
  'primary', 'primary-hover', 'primary-active', 'success', 'warning', 'danger', 'info', 'accent',
  'text-primary', 'text-secondary', 'text-muted', 'text-inverse', 'text-on-primary', 'border', 'border-strong', 'focus',
  'selected', 'disabled', 'shadow', 'scrollbar-track', 'scrollbar-thumb', 'scrollbar-thumb-hover',
  'chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5', 'chart-6',
];

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
const styleFiles = files.filter((path) => extname(path) === '.css' && path !== themesPath);
const paletteUtility = /(?:^|[^\w-])(?:text|bg|border|ring|from|via|to|shadow|placeholder|divide|decoration|outline|accent)-(?:slate|gray|grey|zinc|neutral|stone|amber|yellow|orange|red|rose|green|emerald|teal|blue|sky|cyan|purple|violet|indigo|fuchsia|pink|white|black|gold|brown|lime|tibia)(?:-|\/|\b)/g;
const literalColor = /#[\da-f]{3,8}\b|rgba?\(\s*\d|hsla?\(/gi;
const namedInlineColor = /(?:color|backgroundColor|borderColor)\s*:\s*['"](?:white|black|red|green|blue|yellow|orange|purple|pink|brown|gray|grey)['"]/gi;
const arbitraryColorVariable = /(?:text|bg|border|ring|from|via|to)-\[(?:color:)?var\(/g;
const lowContrastTint = /bg-(primary|success|warning|danger|info|accent)\/(?:3\d|[4-9]\d)\b[^\n"'`]*text-\1\b/g;

const reportMatches = (path, pattern, label) => {
  const source = readFileSync(path, 'utf8');
  for (const match of source.matchAll(pattern)) {
    const line = source.slice(0, match.index).split('\n').length;
    failures.push(`${relative(frontendRoot, path)}:${line}: ${label}: ${match[0].trim()}`);
  }
};

for (const path of sourceFiles) {
  reportMatches(path, paletteUtility, 'non-semantic palette utility');
  reportMatches(path, literalColor, 'hardcoded color');
  reportMatches(path, namedInlineColor, 'hardcoded named color');
  reportMatches(path, arbitraryColorVariable, 'legacy arbitrary color token');
  reportMatches(path, lowContrastTint, 'status text on an overly opaque matching tint');
}
for (const path of styleFiles) {
  reportMatches(path, literalColor, 'hardcoded stylesheet color');
  const source = readFileSync(path, 'utf8');
  if (source.includes('[data-theme=')) failures.push(`${relative(frontendRoot, path)}: theme-specific selector must live in styles/themes.css`);
}

const themeBlock = (theme) => {
  const selector = `[data-theme="${theme}"]`;
  const start = themesSource.indexOf(selector);
  const open = themesSource.indexOf('{', start);
  const close = themesSource.indexOf('}', open);
  return start >= 0 && open >= 0 && close >= 0 ? themesSource.slice(open + 1, close) : '';
};

const parseRgb = (block, token) => {
  const match = block.match(new RegExp(`--ds-${token}:\\s*(\\d+)\\s+(\\d+)\\s+(\\d+)\\s*;`));
  return match ? match.slice(1).map(Number) : null;
};

const luminance = ([red, green, blue]) => {
  const channels = [red, green, blue].map((value) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};

const contrast = (first, second) => {
  const [lighter, darker] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
};

for (const theme of themeIds) {
  const block = themeBlock(theme);
  if (!block) failures.push(`styles/themes.css: missing theme "${theme}"`);
  for (const token of requiredThemeTokens) {
    if (!parseRgb(block, token)) failures.push(`styles/themes.css: theme "${theme}" lacks valid --ds-${token}`);
  }

  const contrastPairs = [
    ['text-primary', 'surface-base', 7],
    ['text-secondary', 'surface', 4.5],
    ['text-muted', 'surface', 4.5],
    ['text-on-primary', 'primary', 4.5],
    ['primary', 'surface-base', 3],
    ['focus', 'surface-base', 3],
    ['success', 'surface', 3],
    ['warning', 'surface', 3],
    ['danger', 'surface', 3],
    ['info', 'surface', 3],
    ['accent', 'surface', 3],
  ];
  for (const [foregroundToken, backgroundToken, minimum] of contrastPairs) {
    const foreground = parseRgb(block, foregroundToken);
    const background = parseRgb(block, backgroundToken);
    if (foreground && background) {
      const ratio = contrast(foreground, background);
      if (ratio < minimum) failures.push(`styles/themes.css: theme "${theme}" contrast ${foregroundToken}/${backgroundToken} is ${ratio.toFixed(2)} (minimum ${minimum})`);
    }
  }
}

for (const primitive of ['ds-container', 'ds-page', 'ds-section', 'ds-panel', 'ds-card', 'ds-toolbar', 'ds-split-view', 'ds-sidebar', 'ds-scrollable-panel']) {
  if (!designSystem.includes(`.${primitive}`)) failures.push(`styles/design-system.css: missing layout primitive .${primitive}`);
}
for (const breakpoint of ['640px', '1024px']) {
  if (!designSystem.includes(`@media (min-width: ${breakpoint})`)) failures.push(`styles/design-system.css: missing responsive breakpoint ${breakpoint}`);
}
for (const selector of ['[data-motion="enhanced"]', '[data-motion="reduced"]', '[data-density="compact"]', '@media (prefers-reduced-motion: reduce)']) {
  if (!designSystem.includes(selector)) failures.push(`styles/design-system.css: missing appearance behavior ${selector}`);
}

const zIndexes = Object.fromEntries([...designSystem.matchAll(/--z-(dropdown|sticky|overlay|modal|toast|tooltip):\s*(\d+);/g)].map((match) => [match[1], Number(match[2])]));
if (!(zIndexes.sticky < zIndexes.dropdown && zIndexes.dropdown < zIndexes.overlay && zIndexes.overlay < zIndexes.modal && zIndexes.modal < zIndexes.toast && zIndexes.toast < zIndexes.tooltip)) {
  failures.push('styles/design-system.css: stacking tokens must increase sticky < dropdown < overlay < modal < toast < tooltip');
}

for (const theme of themeIds) {
  if (!appearanceSource.includes(`'${theme}'`)) failures.push(`context/AppearanceContext.tsx: missing theme "${theme}"`);
  if (!themeSwitcher.includes(theme)) failures.push(`components/ThemeSwitcher.tsx: missing theme "${theme}"`);
}
for (const value of ['system', 'reduced', 'enhanced', 'comfortable', 'compact']) {
  if (!appearanceSource.includes(`'${value}'`)) failures.push(`context/AppearanceContext.tsx: missing appearance option "${value}"`);
}
for (const attribute of ['theme', 'motion', 'density']) {
  if (!appearanceSource.includes(`root.dataset.${attribute}`)) failures.push(`context/AppearanceContext.tsx: does not apply data-${attribute}`);
}
if (!appearanceSource.includes('tibiahub.appearance.v1') || !appearanceSource.includes('JSON.stringify(preferences)')) failures.push('context/AppearanceContext.tsx: unified preference persistence is missing');
if (!designSystem.includes('z-index: var(--z-overlay)') || !designSystem.includes('z-index: var(--z-modal)') || !designSystem.includes('z-index: var(--z-dropdown)')) failures.push('styles/design-system.css: dropdown/dialog semantic layering is incomplete');

if (failures.length) {
  console.error(`Design-system validation failed (${failures.length} issue${failures.length === 1 ? '' : 's'}):`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Design-system validation passed: ${sourceFiles.length} source files, ${styleFiles.length + 1} stylesheets, ${themeIds.length} complete themes with contrast, persistence, motion, density, and layering checks.`);
