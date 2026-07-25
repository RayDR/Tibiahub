import assert from 'node:assert/strict';
import { build } from 'esbuild';

const result = await build({
  entryPoints: [new URL('../src/context/AppearanceContext.tsx', import.meta.url).pathname],
  bundle: true,
  format: 'esm',
  platform: 'node',
  write: false,
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`;
const appearance = await import(moduleUrl);

const values = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  },
};
globalThis.document = { documentElement: { dataset: {} } };

assert.deepEqual(
  appearance.normalizeAppearancePreferences({ theme: 'unknown', motion: 'fast', density: 'tiny' }),
  appearance.DEFAULT_APPEARANCE,
  'invalid preference values must fall back safely',
);

values.set(appearance.APPEARANCE_STORAGE_KEY, JSON.stringify({
  theme: 'midnight-arcana', motion: 'enhanced', density: 'compact',
}));
let initialized = appearance.initializeAppearance();
assert.deepEqual(initialized, { theme: 'midnight-arcana', motion: 'enhanced', density: 'compact' });
assert.deepEqual(globalThis.document.documentElement.dataset, {
  theme: 'midnight-arcana', motion: 'enhanced', density: 'compact',
});

values.clear();
globalThis.document.documentElement.dataset = {};
values.set('theme', 'blood-moon');
initialized = appearance.initializeAppearance();
assert.deepEqual(initialized, { theme: 'blood-moon', motion: 'system', density: 'comfortable' });
assert.equal(values.has('theme'), false, 'legacy theme storage must be retired');
assert.deepEqual(JSON.parse(values.get(appearance.APPEARANCE_STORAGE_KEY)), initialized, 'migrated preferences must use the unified record');

console.log('Appearance persistence passed: sanitization, data attributes, versioned storage, and legacy migration are valid.');
