import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const readRoot = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');
const [dataDisplay, styles, members, users, jobs, review, guildWorkspace, guildService, knowledgeService, workspaceService, pagination, guildBackend, adminBackend, knowledgeBackend, workspaceBackend] = await Promise.all([
  read('src/components/ui/DataDisplay.tsx'),
  read('src/styles/design-system.css'),
  read('src/pages/guild/Members.tsx'),
  read('src/pages/Admin/Users.tsx'),
  read('src/pages/Admin/KnowledgeOperations.tsx'),
  read('src/pages/Admin/KnowledgeRelationshipReview.tsx'),
  read('src/pages/Admin/AdminGuildWorkspace.tsx'),
  read('src/services/guild.ts'),
  read('src/services/knowledge.ts'),
  read('src/services/workspaces.ts'),
  read('src/utils/pagination.ts'),
  readRoot('backend/app/api/v1/endpoints/guild.py'),
  readRoot('backend/app/api/v1/endpoints/admin.py'),
  readRoot('backend/app/api/v1/endpoints/knowledge_admin.py'),
  readRoot('backend/app/api/v1/endpoints/workspaces.py'),
]);

assert.match(dataDisplay, /tabIndex=\{tabIndex\}/);
assert.match(dataDisplay, /export const PaginationControls/);
assert.match(styles, /max-height: max\(12rem, calc\(100dvh/);
assert.match(styles, /\.ds-data-region:focus-visible/);
assert.match(styles, /\.ds-data-region \.ds-table th[^}]*position: sticky/);
assert.match(styles, /\.ds-data-region[^}]*overflow-x: auto[^}]*overflow-y: auto/);

for (const [name, source] of Object.entries({ members, users, guildWorkspace })) {
  assert.match(source, /<DataRegion\b/, `${name} must use the shared bounded region`);
  assert.match(source, /<TableContainer\b/, `${name} must retain table containment`);
  assert.match(source, /<Table\b/, `${name} must retain semantic table markup`);
}
assert.match(members, /const PAGE_SIZE = 12/);
assert.match(members, /setSkip\(0\)/);
assert.match(members, /void load\(0\)/);
assert.match(members, /\[guildName\]/);
assert.match(members, /responsive-card-list/);
assert.match(guildService, /total: number/);
assert.match(guildService, /search\?: string/);
assert.match(guildBackend, /Query\(400, ge=1, le=400\)/);
assert.match(guildBackend, /GuildMemberSnapshot\.id\.asc\(\)/);

assert.match(users, /PAGE_SIZE \+ 1/);
assert.match(users, /requestInFlight\.current/);
assert.match(users, /boundedWindow/);
assert.match(users, /setUsers\(page\.items\)/);
assert.match(users, /additionalError/);
assert.match(adminBackend, /User\.created_at\.desc\(\), User\.id\.desc\(\)/);

for (const [name, source] of Object.entries({ jobs, review, guildWorkspace })) {
  assert.match(source, /<PaginationControls\b/, `${name} needs server-backed page navigation`);
  assert.match(source, /AbortController/, `${name} needs stale-request cancellation`);
  assert.match(source, /retrySkipRef/i, `${name} must preserve the failed page for retry`);
}
assert.match(members, /retrySkipRef/);
assert.match(jobs, /skip: nextSkip/);
assert.match(jobs, /setTotalJobs\(page\.total\)/);
assert.match(review, /setTotal\(page\.total\)/);
assert.match(knowledgeService, /skip\?: number/);
assert.match(knowledgeBackend, /KnowledgeJob\.created_at\.desc\(\), KnowledgeJob\.id\.desc\(\)/);
assert.match(knowledgeBackend, /KnowledgeRelationship\.created_at\.desc\(\), KnowledgeRelationship\.id\.desc\(\)/);

assert.match(workspaceService, /paged: true/);
assert.match(workspaceBackend, /"items": rows, "total": total, "skip": skip, "limit": limit/);
assert.match(workspaceBackend, /WorkspaceAudit\.created_at\.desc\(\), WorkspaceAudit\.id\.desc\(\)/);
assert.doesNotMatch(guildWorkspace, /slice\(0, 20\)/);

const transpiled = ts.transpileModule(pagination, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const helpers = await import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`);
const first = helpers.boundedWindow(Array.from({ length: 51 }, (_, id) => ({ id })), 50);
assert.equal(first.items.length, 50);
assert.equal(first.hasMore, true);
assert.equal(helpers.clampPageSkip(60, 20, 55), 40);
assert.equal(helpers.clampPageSkip(20, 20, 0), 0);

console.log('Phase 2C checks passed: bounded data regions and stable server-backed pagination cover all primary targets.');
