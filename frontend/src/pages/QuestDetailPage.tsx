import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, BookOpen, Crown, Gift, ListOrdered, Loader2, MapPin, ScrollText, ShieldCheck, UserRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { questsApi } from '../services/api';
import type { QuestDetail, QuestItemValue, QuestNamedValue, QuestRelationship } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import MapMetadataPanel from '../components/MapMetadataPanel';
import { Page } from '../components/ui';
import { KnowledgeEmpty, KnowledgeFact, KnowledgeFacts, KnowledgeSection } from '../components/knowledge/KnowledgeDetail';
import { SuggestCorrectionLink } from '../components/feedback/GitHubFeedbackLink';
import { useSeoMetadata } from '../utils/seo';
import {
  createCyclopediaRouteState,
  resolveCyclopediaReturnTarget,
} from '../utils/cyclopediaNavigation';

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
  linkState,
}: {
  values: QuestNamedValue[];
  relationships: QuestRelationship[];
  entity: 'npc' | 'location';
  linkState?: unknown;
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
      ? <Link to={`/${entity === 'npc' ? 'npcs' : 'locations'}/${resolved.target_slug}`} state={linkState} className="flex min-h-11 items-center justify-between gap-3 rounded-lg border border-primary/25 bg-surface-base/60 px-3 py-2 hover:border-primary/60 hover:text-content-primary">{content}</Link>
      : <div className="flex min-h-11 items-center rounded-lg border border-line bg-surface-base/60 px-3 py-2">{content}</div>}
    </li>;
  })}</ul>;
}

export default function QuestDetailPage() {
  const { t } = useTranslation();
  const { questId } = useParams<{ questId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isAuthenticated } = useAuth();
  useSeoMetadata(quest ? {
    title: `${quest.name} — Tibia quest`,
    description: quest.summary || quest.description || `Requirements, missions, rewards and access for ${quest.name}.`,
    canonicalPath: `/quests/${quest.slug || quest.id}`,
    type: 'article',
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }, { name: quest.name, path: `/quests/${quest.slug || quest.id}` }],
  } : null);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      if (!questId) return;
      try {
        setLoading(true); setError(null);
        const data = await questsApi.getById(questId, controller.signal);
        setQuest(data);
        if (data.slug && data.slug !== questId) navigate(`/quests/${data.slug}`, { replace: true, state: location.state });
        if (isAuthenticated && data.id) void activityApi.record({ activity_type: 'view_quest', entity_type: 'quest', entity_id: String(data.id), metadata: { name: data.name } }).catch(() => undefined);
      } catch {
        setError(t('questDetail.notFound'));
      } finally { setLoading(false); }
    };
    void run();
    return () => controller.abort();
  }, [questId, isAuthenticated, location.state, navigate, t]);

  const backTarget = resolveCyclopediaReturnTarget(
    (location.state as { from?: string } | null)?.from,
    '/cyclopedia?tab=quests',
  );
  const cyclopediaState = createCyclopediaRouteState(backTarget);
  if (loading) return <Page><div className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /></div></Page>;
  if (!quest || error) return <Page><div className="mx-auto max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-6 text-danger"><div className="mb-3 text-lg font-semibold">{t('questDetail.unavailable')}</div><p className="text-sm text-danger/80">{error || t('questDetail.notFound')}</p></div></Page>;

  const requirementCount = quest.required_items.length + quest.required_quests.length;
  const sections = [
    ['overview', t('questDetail.overview')],
    ['requirements', t('questDetail.requirements', { count: requirementCount })],
    ['missions', t('questDetail.missions', { count: quest.missions.length })],
    ['rewards', t('questDetail.rewards', { count: quest.rewarded_items.length })],
    ['connections', t('questDetail.connections')],
  ];
  return <Page><div>
    <button onClick={() => navigate(backTarget)} className="mb-6 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft size={18} />{t('questDetail.back')}</button>
    <article className="quest-codex relative overflow-hidden rounded-3xl border border-line-strong bg-surface-base/70 shadow-sm">
      <div className="quest-codex__binding h-2 bg-gradient-to-r from-primary-active via-primary to-primary-active" />
      <div className="quest-codex__pages p-5 sm:p-8 lg:p-10">
      <header id="overview" className="quest-codex__title scroll-mt-24 border-b border-line pb-8 text-center"><ScrollText className="mx-auto text-primary" size={36} /><p className="mt-3 text-xs font-bold uppercase tracking-[0.25em] text-primary">{t('questDetail.codexEntry')}</p><h1 className="mx-auto mt-3 max-w-4xl font-serif text-3xl font-bold text-content-primary sm:text-5xl">{quest.name}</h1>{quest.group_name && <p className="mt-2 text-sm text-primary">{t('questDetail.group', { name: quest.group_name })}</p>}<p className="mx-auto mt-6 max-w-3xl text-left text-lg leading-8 text-content-secondary sm:text-center">{quest.summary || quest.description || t('questDetail.noDetails')}</p><Link to={`/map?entityType=quest&slug=${encodeURIComponent(quest.slug || quest.name)}&q=${encodeURIComponent(quest.name)}`} className="app-button-secondary app-button-sm mt-4 inline-flex"><MapPin size={14} />{t('map.openDetails')}</Link></header>
      <div className="mt-6"><KnowledgeFacts><KnowledgeFact label={t('questDetail.minimumLevel')} value={quest.min_level ?? t('questDetail.notAvailable')} /><KnowledgeFact label={t('questDetail.experience')} value={quest.experience_reward?.toLocaleString() ?? t('questDetail.notAvailable')} /><KnowledgeFact label={t('questDetail.premium')} value={quest.premium_required == null ? t('questDetail.unknown') : t(quest.premium_required ? 'questDetail.yes' : 'questDetail.no')} /><KnowledgeFact label={t('questDetail.repeatable')} value={quest.repeatable == null ? t('questDetail.unknown') : t(quest.repeatable ? 'questDetail.yes' : 'questDetail.no')} /></KnowledgeFacts></div>
      <nav aria-label={t('questDetail.contents')} className="quest-codex__contents my-8 rounded-2xl border border-line bg-surface-raised p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold text-content-primary"><BookOpen size={17} className="text-primary" />{t('questDetail.contents')}</div><ol className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">{sections.map(([id, label], index) => <li key={id}><a href={`#${id}`} className="flex min-h-10 items-center gap-2 rounded-lg px-2 text-content-secondary hover:bg-surface-hover hover:text-primary"><span className="font-serif text-primary">{index + 1}.</span>{label}</a></li>)}</ol></nav>
      <div className="quest-codex__spread grid gap-6 lg:grid-cols-2">
        <KnowledgeSection id="requirements" title={t('questDetail.requirements', { count: requirementCount })} icon={<ShieldCheck size={20} />}><div className="space-y-5">{quest.required_items.length > 0 && <div><h3 className="mb-2 text-sm font-semibold text-content-primary">{t('questDetail.items')}</h3><Items values={quest.required_items} /></div>}{quest.required_quests.length > 0 && <div><h3 className="mb-2 text-sm font-semibold text-content-primary">{t('questDetail.quests')}</h3><Names values={quest.required_quests} /></div>}{requirementCount === 0 && <KnowledgeEmpty>{t('questDetail.noRequirements')}</KnowledgeEmpty>}</div></KnowledgeSection>
        <KnowledgeSection id="rewards" title={t('questDetail.rewards', { count: quest.rewarded_items.length })} icon={<Gift size={20} />}>{quest.rewarded_items.length ? <Items values={quest.rewarded_items} /> : <KnowledgeEmpty>{t('questDetail.noRewards')}</KnowledgeEmpty>}</KnowledgeSection>
      </div>
      <KnowledgeSection id="missions" className="mt-6" title={t('questDetail.missions', { count: quest.missions.length })} icon={<ListOrdered size={20} />}><div className="space-y-6">{quest.missions.length ? quest.missions.map(mission => { const missionRelationships = quest.relationships.filter(relationship => relationship.mission_id === mission.id); return <article key={mission.id} className="quest-codex__mission relative border-l-2 border-primary/40 pl-6"><div className="absolute -left-4 top-0 grid size-8 place-items-center rounded-full border border-primary bg-surface text-sm font-bold text-primary">{mission.sequence}</div><p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{t('questDetail.chapter', { number: mission.sequence })}</p><h3 className="mt-1 font-serif text-xl font-bold text-content-primary">{mission.title}</h3>{mission.description && <p className="mt-3 whitespace-pre-line text-sm leading-7 text-content-secondary">{mission.description}</p>}{mission.objectives.length > 0 && <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-content-secondary">{mission.objectives.map((value, index) => <li key={index}>{value}</li>)}</ul>}<div className="mt-4 grid gap-4 sm:grid-cols-2">{mission.related_npcs.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-muted">{t('questDetail.npcs')}</h4><EntityReferences values={mission.related_npcs} relationships={missionRelationships} entity="npc" linkState={cyclopediaState} /></div>}{mission.locations.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-muted">{t('questDetail.locations')}</h4><EntityReferences values={mission.locations} relationships={missionRelationships} entity="location" linkState={cyclopediaState} /></div>}</div></article>; }) : <KnowledgeEmpty>{t('questDetail.noMissions')}</KnowledgeEmpty>}</div></KnowledgeSection>
      <div id="connections" className="quest-codex__spread mt-6 grid scroll-mt-24 gap-4 md:grid-cols-2">
        {(quest.starting_npcs.length > 0 || quest.related_npcs.length > 0) && <section className="rounded-xl border border-line p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-primary"><UserRound size={16} />{t('questDetail.npcs')}</h2><EntityReferences values={[...quest.starting_npcs, ...quest.related_npcs]} relationships={quest.relationships.filter(relationship => !relationship.mission_id)} entity="npc" linkState={cyclopediaState} /></section>}
        {quest.locations.length > 0 && <section className="rounded-xl border border-line p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-primary"><MapPin size={16} />{t('questDetail.locations')}</h2><EntityReferences values={quest.locations} relationships={quest.relationships.filter(relationship => !relationship.mission_id)} entity="location" linkState={cyclopediaState} /></section>}
      </div>
      {quest.access_unlocks.length > 0 && <KnowledgeSection className="mt-6" title={t('questDetail.access')}><Names values={quest.access_unlocks} /></KnowledgeSection>}
      <section className="mt-6"><h2 className="mb-3 font-serif text-xl font-bold text-primary">{t('questDetail.creatures')}</h2>{quest.related_creatures.length ? <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{quest.related_creatures.map(creature => <Link to={`/creatures/${creature.creature_slug || creature.creature_id}`} state={cyclopediaState} key={creature.creature_id} className="flex items-center gap-3 rounded-xl border border-line bg-surface-raised p-3 hover:border-primary/40"><img src={`/api/v1/creatures/${creature.creature_id}/image`} alt="" className="size-16 object-contain" /><div><div className="flex items-center gap-2 text-content-primary">{creature.is_boss && <Crown size={14} className="text-danger" />}<span className="font-semibold">{creature.creature_name}</span></div><div className="mt-1 text-xs text-content-secondary">{creature.classification || t('questDetail.unknownClassification')}</div></div></Link>)}</div> : <KnowledgeEmpty>{t('questDetail.noCreatures')}</KnowledgeEmpty>}</section>
      <MapMetadataPanel entityId={quest.knowledge_entity_id} />
      <footer className="mt-6 flex flex-wrap items-center gap-3 border-t border-line pt-4 text-xs text-content-muted">{quest.last_synced_at && <span>{t('questDetail.updated', { date: new Date(quest.last_synced_at).toLocaleString() })}</span>}{quest.source_url && <a href={quest.source_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{t('questDetail.source')}</a>}</footer>
      <div className="mt-5 flex justify-end"><SuggestCorrectionLink entityType="Quest" entityName={quest.name} /></div>
      </div>
    </article>
  </div></Page>;
}
