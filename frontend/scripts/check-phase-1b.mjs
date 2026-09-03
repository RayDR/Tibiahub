import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const [app, dataTools, adminLayout, announcements, paginationSource] = await Promise.all([
  read('src/App.tsx'),
  read('src/pages/Admin/DataTools.tsx'),
  read('src/layouts/AdminLayout.tsx'),
  read('src/pages/guild/Announcements.tsx'),
  read('src/pages/guild/announcementPagination.ts'),
]);

const databaseRoute = app.slice(app.indexOf('path="database-sync"'), app.indexOf('path="database-sync"') + 220);
const syncRoute = app.slice(app.indexOf('path="sync"'), app.indexOf('path="sync"') + 180);
assert.match(databaseRoute, /Navigate to="\/admin\/sync" replace/);
assert.match(syncRoute, /DataTools initialTab="admin-sync"/);
assert.match(adminLayout, /path: '\/admin\/sync'/);
assert.doesNotMatch(dataTools, /db-sync|DBSyncTab|Database Sync|sync\/preview|sync\/approve/);
assert.match(dataTools, /id: 'admin-sync', label: t\('adminDataTools\.tabs\.sync'\)/);
assert.match(dataTools, /id: 'knowledge'/);
assert.match(app, /path="knowledge"[\s\S]{0,120}initialTab="knowledge"/);

assert.match(announcements, /requestInFlight\.current/);
assert.match(announcements, /page\.initialError/);
assert.match(announcements, /page\.additionalError/);
assert.match(announcements, /t\("announcementUI\.retryMore"\)/);

const transpiled = ts.transpileModule(paginationSource, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const pagination = await import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`);
const { emptyAnnouncementPage, loadAnnouncementWindow } = pagination;

const windows = new Map([
  [0, [{ id: 1 }, { id: 2 }]],
  [2, [{ id: 3 }, { id: 4 }]],
  [4, [{ id: 5 }]],
]);
const requested = [];
const request = async (skip) => {
  requested.push(skip);
  return windows.get(skip) || [];
};

let state = emptyAnnouncementPage();
let result = await loadAnnouncementWindow({ state, reset: true, limit: 2, guildName: 'Guild A', request });
assert.equal(result.error, null);
assert.deepEqual(result.state.items.map((item) => item.id), [1, 2]);
assert.equal(result.state.nextSkip, 2);
state = result.state;

result = await loadAnnouncementWindow({ state, reset: false, limit: 2, guildName: 'Guild A', request });
assert.deepEqual(result.state.items.map((item) => item.id), [1, 2, 3, 4]);
assert.equal(result.requestedSkip, 2);
state = result.state;

result = await loadAnnouncementWindow({ state, reset: false, limit: 2, guildName: 'Guild A', request });
assert.deepEqual(result.state.items.map((item) => item.id), [1, 2, 3, 4, 5]);
assert.equal(result.state.hasMore, false);
assert.deepEqual(requested, [0, 2, 4]);

result = await loadAnnouncementWindow({ state: result.state, reset: true, limit: 2, guildName: 'Guild B', request });
assert.deepEqual(result.state.items.map((item) => item.id), [1, 2]);
assert.equal(result.requestedSkip, 0);

let failInitial = true;
const retryInitial = async () => {
  if (failInitial) {
    failInitial = false;
    throw new Error('offline');
  }
  return [{ id: 10 }, { id: 11 }];
};
state = emptyAnnouncementPage();
result = await loadAnnouncementWindow({ state, reset: true, limit: 2, guildName: 'Guild A', request: retryInitial });
assert.equal(result.state.initialError, true);
assert.deepEqual(result.state.items, []);
result = await loadAnnouncementWindow({ state: result.state, reset: true, limit: 2, guildName: 'Guild A', request: retryInitial });
assert.equal(result.state.initialError, false);
assert.deepEqual(result.state.items.map((item) => item.id), [10, 11]);

state = result.state;
let failMore = true;
const retryMore = async (skip) => {
  assert.equal(skip, 2);
  if (failMore) {
    failMore = false;
    throw new Error('temporary');
  }
  return [{ id: 12 }];
};
result = await loadAnnouncementWindow({ state, reset: false, limit: 2, guildName: 'Guild A', request: retryMore });
assert.equal(result.state.additionalError, true);
assert.deepEqual(result.state.items.map((item) => item.id), [10, 11]);
assert.equal(result.state.nextSkip, 2);
result = await loadAnnouncementWindow({ state: result.state, reset: false, limit: 2, guildName: 'Guild A', request: retryMore });
assert.equal(result.state.additionalError, false);
assert.deepEqual(result.state.items.map((item) => item.id), [10, 11, 12]);

console.log('Phase 1B checks passed: durable sync routing and announcement pagination/error retries are correct.');
