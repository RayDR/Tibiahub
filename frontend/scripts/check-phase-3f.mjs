import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8');
const fail = (message) => {
  console.error(`Phase 3F check failed: ${message}`);
  process.exitCode = 1;
};
const requireText = (source, value, message) => {
  if (!source.includes(value)) fail(message);
};

const planner = read('src/pages/guild/GuildHuntPlanner.tsx');
const picker = read('src/components/guild/CanonicalHuntZonePicker.tsx');
const client = read('src/services/huntPlanner.ts');
const apiClient = read('src/services/api.ts');
const backend = read('../backend/app/services/guild_hunt_service.py');
const endpoint = read('../backend/app/api/v1/endpoints/hunts.py');
const zoneEndpoint = read('../backend/app/api/v1/hunt_zones.py');
const model = read('../backend/app/models/hunt.py');

requireText(model, 'hunting_zone_id = Column(', 'GuildHunt lacks the nullable canonical identity field');
requireText(model, 'ForeignKey("knowledge_entities.uuid", ondelete="RESTRICT")', 'historical hunts are not protected from canonical entity deletion');
requireText(backend, 'entity.entity_type != "hunt_zone"', 'backend does not reject cross-entity-type references');
requireText(backend, 'entity.status != "active"', 'new links do not enforce current canonical Knowledge');
requireText(backend, 'zone_summaries(db: Session, hunts:', 'batched calendar summary projection is missing');
requireText(endpoint, 'zone_summaries = GuildHuntPlannerService.zone_summaries(db, hunts)', 'calendar endpoint does not batch zone context');
requireText(zoneEndpoint, 'canonical_only: bool', 'canonical-only discovery contract is missing');
requireText(zoneEndpoint, 'KnowledgeEntity.status == "active"', 'picker API can expose retired entities');

requireText(apiClient, 'canonical_only?: boolean', 'frontend API cannot request canonical-only zones');
requireText(picker, 'canonical_only: true', 'picker does not exclude legacy HuntZones');
requireText(picker, 'window.setTimeout', 'picker search is not debounced');
requireText(picker, 'controller.abort()', 'stale picker searches are not cancelled');
requireText(picker, 'role="combobox"', 'picker lacks the accessible combobox contract');
requireText(picker, 'aria-activedescendant', 'picker lacks keyboard active-result semantics');
requireText(picker, "event.key === 'ArrowDown'", 'picker lacks arrow-key navigation');
requireText(picker, 'access_required === true', 'access Quest UI does not distinguish required access');
requireText(picker, 'to={`/quests/${quest.slug || quest.id}`}', 'resolved required Quest navigation is missing');
requireText(picker, 'zone.creature_preview', 'bounded Creature preview is missing');
requireText(picker, 'creature.is_boss', 'authoritative Boss distinction is missing');
requireText(picker, 'buildMapEntityUrl', 'picker does not use the Phase 3D canonical map contract');
requireText(picker, "t('huntPlanner.zone.noGeometry')", 'no-geometry messaging is not wired');
if (/avg_(exp|profit)_hour\s*\|\|\s*0/.test(picker)) fail('unknown EXP/profit is rendered as zero');
if (/https?:\/\//.test(picker)) fail('picker contains a direct media hotlink');
if (/#[0-9a-f]{3,8}\b|rgba?\(/i.test(picker)) fail('picker contains raw colors');
if (/max-h-\d+.*overflow-y-auto/.test(picker)) fail('picker adds a nested result scroller inside the dialog');

requireText(client, 'hunting_zone_id?: string | null', 'create/edit payload lacks canonical identity');
requireText(planner, "hunting_zone_id: zoneMode === 'canonical'", 'form does not send canonical identity separately');
requireText(planner, "onModeChange={setZoneMode}", 'custom/canonical edit transitions are missing');
requireText(planner, 'hunt.hunting_zone_summary', 'calendar cards do not consume lightweight zone context');
requireText(planner, 'setSubmitError(true)', 'failed mutation does not preserve an explicit retry state');

if (!process.exitCode) {
  console.log('Phase 3F checks passed: optional canonical identity, legacy protection, batched summaries, accessible picker, access/Creature preview, and canonical map navigation are present.');
}
