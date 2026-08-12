import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';

const utilityPath = new URL('../src/utils/assistantSuggestions.ts', import.meta.url).pathname;
const result = await build({ entryPoints: [utilityPath], bundle: true, format: 'esm', platform: 'node', write: false });
const moduleUrl = `data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`;
const utility = await import(moduleUrl);

const suggestions = [
  { id: '1', text: 'Where can I hunt Werewolves?', entity_type: 'creature' },
  { id: '2', text: 'How can I get Ice Flower Seeds?', entity_type: 'item' },
  { id: '3', text: 'What do I need to start The Inquisition Quest?', entity_type: 'quest' },
  { id: '4', text: 'How do I get to Roshamuul?', entity_type: 'hunt_zone' },
];

assert.equal(utility.findSuggestionCompletion('', suggestions), null);
assert.equal(utility.findSuggestionCompletion('where can i', suggestions)?.id, '1');
assert.equal(utility.findSuggestionCompletion('Where can I hunt Werewolves?', suggestions), null);
assert.equal(utility.findSuggestionCompletion('unrelated question', suggestions), null);
assert.deepEqual(
  utility.selectVisibleSuggestions(suggestions, 'stable-seed').map((row) => row.id),
  utility.selectVisibleSuggestions(suggestions, 'stable-seed').map((row) => row.id),
  'rotation must be deterministic for a conversation',
);
assert.equal(new Set(utility.selectVisibleSuggestions(suggestions, 'stable-seed').map((row) => row.entity_type)).size, 3);

const heroUtilityPath = new URL('../src/utils/assistantHeroCopy.ts', import.meta.url).pathname;
const heroResult = await build({ entryPoints: [heroUtilityPath], bundle: true, format: 'esm', platform: 'node', write: false });
const heroModuleUrl = `data:text/javascript;base64,${Buffer.from(heroResult.outputFiles[0].text).toString('base64')}`;
const heroUtility = await import(heroModuleUrl);
const morning = new Date(2026, 7, 12, 8, 0, 0);
assert.equal(heroUtility.daypartFromHour(8), 'morning');
assert.equal(heroUtility.daypartFromHour(14), 'afternoon');
assert.equal(heroUtility.daypartFromHour(22), 'evening');
assert.deepEqual(
  heroUtility.selectAssistantHeroCopy('es', morning, 'stable-session'),
  heroUtility.selectAssistantHeroCopy('es', morning, 'stable-session'),
  'hero copy must be stable within the same local daypart and session',
);
assert.notEqual(
  heroUtility.selectAssistantHeroCopy('en', morning, 'stable-session').headline,
  heroUtility.selectAssistantHeroCopy('es', morning, 'stable-session').headline,
  'hero copy must follow the active locale',
);

const chat = readFileSync(new URL('../src/components/assistant/AssistantChat.tsx', import.meta.url), 'utf8');
assert.match(chat, /entries\.length === 0 && !message/, 'starter chips must hide as soon as typing begins');
assert.match(chat, /event\.key === 'Tab' && completion/, 'Tab completion must require a candidate');
assert.match(chat, /event\.preventDefault\(\); setMessage\(completion\.text\)/, 'Tab must fill without submitting');
assert.match(chat, /event\.key === 'Enter' && !event\.shiftKey/, 'Enter submission behavior must remain');
assert.match(chat, /sessionStorage/, 'conversation persistence must remain');
assert.match(chat, /AbortController/, 'request cancellation must remain');
assert.match(chat, /rows=\{1\}/, 'composer must start as a visually centered single line');
assert.match(chat, /Math\.min\(textarea\.scrollHeight, 160\)/, 'composer must grow to a bounded height');
assert.match(chat, /assistant-suggestion/, 'suggestions must use the mobile-first presentation');

console.log('Assistant interaction checks passed: deterministic rotation, quiet typing, accessible Tab completion, and preserved chat behavior.');
