import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const importBundled = async path => {
  const entry = new URL(`../${path}`, import.meta.url).pathname;
  const bundle = await build({ entryPoints: [entry], bundle: true, format: 'esm', platform: 'node', write: false });
  const url = `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`;
  return import(url);
};

const { availableItemMediaUrl } = await importBundled('src/utils/entityMedia.ts');
const local = '/api/v1/items/00000000-0000-0000-0000-000000000001/image?placeholder=false';
assert.equal(availableItemMediaUrl({ status: 'available', url: local }), local);
assert.equal(availableItemMediaUrl({ status: 'unavailable', url: local }), undefined);
assert.equal(availableItemMediaUrl({ status: 'available', url: 'https://tibia.fandom.com/item.gif' }), undefined);
assert.equal(availableItemMediaUrl({ status: 'available', url: '/api/v1/items/id/image' }), undefined);

const itemSurfaces = [
  'src/pages/ItemDetailPage.tsx',
  'src/pages/CreaturesPage.tsx',
  'src/components/LootDisplay.tsx',
  'src/components/search/KnowledgeSearchBox.tsx',
  'src/components/quest/QuestReference.tsx',
  'src/components/cyclopedia/CyclopediaPersonalHistoryStrip.tsx',
  'src/components/CyclopediaDiscovery.tsx',
];
for (const path of itemSurfaces) {
  const source = read(path);
  assert.doesNotMatch(source, /item_image_url/, `${path} must not render provider Item media`);
  assert.doesNotMatch(source, /\/api\/v1\/items\/\$\{[^}]*?(?:image_item_id|\.id)[^}]*\}\/image/, `${path} must not construct ambiguous Item image URLs`);
  assert.doesNotMatch(source, /tibia\.fandom\.com|static\.wikia\.nocookie\.net/i, `${path} must not introduce an external media host`);
}

assert.match(read('src/pages/ItemDetailPage.tsx'), /availableItemMediaUrl\(item\?\.media\)/);
assert.match(read('src/pages/CreaturesPage.tsx'), /availableItemMediaUrl\(item\.media\)/);
assert.match(read('src/components/LootDisplay.tsx'), /availableItemMediaUrl\(loot\.media\)/);
assert.match(read('src/components/ImageWithFallback.tsx'), /onError=\{\(\) =>/);

const npcMedia = read('src/utils/npcCyclopedia.ts');
assert.match(npcMedia, /\/api\/v1\/npcs\//, 'NPC local media contract must remain unchanged');
assert.doesNotMatch(npcMedia, /tibia\.fandom\.com|static\.wikia\.nocookie\.net/i);

console.log('Phase 4.2C checks passed: Item media is backend-authored, local-only, verified, and unambiguous.');
