import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Crown, Loader2, MapPin, ScrollText, UserRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { questsApi } from '../services/api';
import type { QuestDetail, QuestItemValue, QuestNamedValue, QuestRelationship } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import MapMetadataPanel from '../components/MapMetadataPanel';

function Names({ values }: { values: QuestNamedValue[] }) {
  return <ul className="space-y-2">{values.map((value, index) => <li key={`${value.name}-${index}`} className="rounded-lg border border-line bg-surface-base/60 px-3 py-2 text-sm text-content-secondary">{value.name}</li>)}</ul>;
}

function Items({ values }: { values: QuestItemValue[] }) {
  return <ul className="space-y-2">{values.map((value, index) => <li key={`${value.name}-${index}`} className="rounded-lg border border-line bg-surface-base/60 px-3 py-2 text-sm text-content-secondary">{value.amount > 1 ? `${value.amount}× ` : ''}{value.name}{value.note ? ` — ${value.note}` : ''}</li>)}</ul>;
}

function EntityReferences({
  values,
  relationships,
  entity,
}: {
  values: QuestNamedValue[];
  relationships: QuestRelationship[];
  entity: 'npc' | 'location';
}) {
  const { t } = useTranslation();
  const deduplicated = values.filter((value, index) => (
    values.findIndex(candidate => candidate.name.trim().toLocaleLowerCase() === value.name.trim().toLocaleLowerCase()) === index
  ));
  return <ul className="space-y-2">{deduplicated.map((value) => {
    const normalized = value.name.trim().toLocaleLowerCase();
    const resolved = relationships.find((relationship) => (
      relationship.resolution_status === 'resolved'
      && relationship.target_slug
      && relationship.target_name.trim().toLocaleLowerCase() === normalized
      && (entity === 'npc'
        ? relationship.target_entity_type === 'npc'
        : ['location', 'area', 'town'].includes(relationship.target_entity_type))
    ));
    const content = <><span>{value.name}</span>{resolved && <span className="flex items-center gap-1 text-xs text-primary">{t(`questDetail.open${entity === 'npc' ? 'Npc' : 'Location'}`)}<ArrowUpRight size={13} /></span>}</>;
    return <li key={normalized} className="text-sm text-content-secondary">{resolved
      ? <Link to={`/${entity === 'npc' ? 'npcs' : 'locations'}/${resolved.target_slug}`} className="flex min-h-11 items-center justify-between gap-3 rounded-lg border border-primary/25 bg-surface-base/60 px-3 py-2 hover:border-primary/60 hover:text-content-primary">{content}</Link>
      : <div className="flex min-h-11 items-center rounded-lg border border-line bg-surface-base/60 px-3 py-2">{content}</div>}
    </li>;
  })}</ul>;
}

export default function QuestDetailPage() {
  const { t } = useTranslation();
  const { questId } = useParams<{ questId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      if (!questId) return;
      try {
        setLoading(true); setError(null);
        const data = await questsApi.getById(questId, controller.signal);
        setQuest(data);
        if (isAuthenticated && data.id) void activityApi.record({ activity_type: 'view_quest', entity_type: 'quest', entity_id: String(data.id), metadata: { name: data.name } }).catch(() => undefined);
      } catch {
        setError(t('questDetail.notFound'));
      } finally { setLoading(false); }
    };
    void run();
    return () => controller.abort();
  }, [questId, isAuthenticated, t]);

  const unresolved = useMemo(() => quest?.relationships.filter(item => item.resolution_status !== 'resolved').length || 0, [quest]);
  if (loading) return <div className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /></div>;
  if (!quest || error) return <div className="mx-auto mt-20 max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-6 text-danger"><div className="mb-3 text-lg font-semibold">{t('questDetail.unavailable')}</div><p className="text-sm text-danger/80">{error || t('questDetail.notFound')}</p></div>;

  const requirementCount = quest.required_items.length + quest.required_quests.length;
  return <div className="pb-12 pt-6"><div>
    <button onClick={() => navigate('/cyclopedia')} className="mb-6 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft size={18} />{t('questDetail.back')}</button>
    <article className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6">
      <header className="mb-5"><div className="flex items-start gap-3 text-primary"><ScrollText className="mt-1 shrink-0" size={24} /><div><h1 className="text-2xl font-bold text-content-primary sm:text-3xl">{quest.name}</h1>{quest.group_name && <p className="mt-1 text-xs text-primary">{t('questDetail.group', { name: quest.group_name })}</p>}</div></div><p className="mt-4 text-content-secondary">{quest.summary || quest.description || t('questDetail.noDetails')}</p></header>
      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
        <div className="rounded-lg bg-surface-base/60 p-3 text-content-secondary">{t('questDetail.minimumLevel')}: {quest.min_level ?? t('questDetail.notAvailable')}</div>
        <div className="rounded-lg bg-surface-base/60 p-3 text-content-secondary">{t('questDetail.experience')}: {quest.experience_reward ?? t('questDetail.notAvailable')}</div>
        <div className="rounded-lg bg-surface-base/60 p-3 text-content-secondary">{t('questDetail.premium')}: {quest.premium_required == null ? t('questDetail.unknown') : t(quest.premium_required ? 'questDetail.yes' : 'questDetail.no')}</div>
        <div className="rounded-lg bg-surface-base/60 p-3 text-content-secondary">{t('questDetail.repeatable')}: {quest.repeatable == null ? t('questDetail.unknown') : t(quest.repeatable ? 'questDetail.yes' : 'questDetail.no')}</div>
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <details open className="rounded-xl border border-line p-4"><summary className="cursor-pointer font-semibold text-primary">{t('questDetail.requirements', { count: requirementCount })}</summary><div className="mt-3 space-y-4">{quest.required_items.length > 0 && <div><h3 className="mb-2 text-sm text-content-secondary">{t('questDetail.items')}</h3><Items values={quest.required_items} /></div>}{quest.required_quests.length > 0 && <div><h3 className="mb-2 text-sm text-content-secondary">{t('questDetail.quests')}</h3><Names values={quest.required_quests} /></div>}{requirementCount === 0 && <p className="text-sm text-content-muted">{t('questDetail.noRequirements')}</p>}</div></details>
        <details open className="rounded-xl border border-line p-4"><summary className="cursor-pointer font-semibold text-primary">{t('questDetail.rewards', { count: quest.rewarded_items.length })}</summary><div className="mt-3">{quest.rewarded_items.length ? <Items values={quest.rewarded_items} /> : <p className="text-sm text-content-muted">{t('questDetail.noRewards')}</p>}</div></details>
      </div>
      <details open className="mt-6 rounded-xl border border-line p-4"><summary className="cursor-pointer font-semibold text-primary">{t('questDetail.missions', { count: quest.missions.length })}</summary><div className="mt-3 space-y-3">{quest.missions.length ? quest.missions.map(mission => { const missionRelationships = quest.relationships.filter(relationship => relationship.mission_id === mission.id); return <article key={mission.id} className="rounded-lg bg-surface-base/60 p-4"><h3 className="font-semibold text-content-primary">{mission.sequence}. {mission.title}</h3>{mission.description && <p className="mt-2 text-sm text-content-secondary">{mission.description}</p>}{mission.objectives.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">{mission.objectives.map((value, index) => <li key={index}>{value}</li>)}</ul>}<div className="mt-3 grid gap-3 sm:grid-cols-2">{mission.related_npcs.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-muted">{t('questDetail.npcs')}</h4><EntityReferences values={mission.related_npcs} relationships={missionRelationships} entity="npc" /></div>}{mission.locations.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-muted">{t('questDetail.locations')}</h4><EntityReferences values={mission.locations} relationships={missionRelationships} entity="location" /></div>}</div></article>; }) : <p className="text-sm text-content-muted">{t('questDetail.noMissions')}</p>}</div></details>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {(quest.starting_npcs.length > 0 || quest.related_npcs.length > 0) && <section className="rounded-xl border border-line p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-primary"><UserRound size={16} />{t('questDetail.npcs')}</h2><EntityReferences values={[...quest.starting_npcs, ...quest.related_npcs]} relationships={quest.relationships.filter(relationship => !relationship.mission_id)} entity="npc" /></section>}
        {quest.locations.length > 0 && <section className="rounded-xl border border-line p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-primary"><MapPin size={16} />{t('questDetail.locations')}</h2><EntityReferences values={quest.locations} relationships={quest.relationships.filter(relationship => !relationship.mission_id)} entity="location" /></section>}
      </div>
      {quest.access_unlocks.length > 0 && <details className="mt-6 rounded-xl border border-line p-4"><summary className="cursor-pointer font-semibold text-primary">{t('questDetail.access')}</summary><div className="mt-3"><Names values={quest.access_unlocks} /></div></details>}
      <section className="mt-6"><h2 className="mb-2 text-lg font-semibold text-primary">{t('questDetail.creatures')}</h2>{quest.related_creatures.length ? <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{quest.related_creatures.map(creature => <Link to={`/creatures/${creature.creature_slug || creature.creature_id}`} key={creature.creature_id} className="rounded-lg border border-line bg-surface-base/60 p-3 hover:border-primary/40"><div className="flex items-center gap-2 text-content-primary">{creature.is_boss && <Crown size={14} className="text-danger" />}<span className="font-semibold">{creature.creature_name}</span></div><div className="mt-1 text-xs text-content-secondary">{creature.classification || t('questDetail.unknownClassification')}</div></Link>)}</div> : <p className="text-sm text-content-muted">{t('questDetail.noCreatures')}</p>}</section>
      <MapMetadataPanel entityId={quest.knowledge_entity_id} />
      <footer className="mt-6 flex flex-wrap items-center gap-3 text-xs text-content-muted">{quest.last_synced_at && <span>{t('questDetail.updated', { date: new Date(quest.last_synced_at).toLocaleString() })}</span>}{unresolved > 0 && <span>{t('questDetail.referencesPending', { count: unresolved })}</span>}{quest.source_url && <a href={quest.source_url} target="_blank" rel="noreferrer" className="text-primary hover:text-primary">{t('questDetail.source')}</a>}</footer>
    </article>
  </div></div>;
}
