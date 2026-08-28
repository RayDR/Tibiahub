import { useEffect, useState, type ReactNode } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, Crown, Gift, ListOrdered, Loader2, MapPin, ScrollText, ShieldCheck, UserRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import '../i18n/questEnhancements';
import { questsApi } from '../services/api';
import type { QuestDetail, QuestNamedValue, QuestRelationship } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import { Page } from '../components/ui';
import { KnowledgeEmpty, KnowledgeSection } from '../components/knowledge/KnowledgeDetail';
import RichEntityLink from '../components/knowledge/RichEntityLink';
import QuestCompletionControl from '../components/quest/QuestCompletionControl';
import QuestMapInsets from '../components/quest/QuestMapInsets';
import QuestReference from '../components/quest/QuestReference';
import { SuggestCorrectionLink } from '../components/feedback/GitHubFeedbackLink';
import { useSeoMetadata } from '../utils/seo';
import {
  createCyclopediaRouteState,
  resolveCyclopediaReturnTarget,
} from '../utils/cyclopediaNavigation';
import { hasDetailedQuestData } from '../utils/questPresentation';

function Names({ values }: { values: QuestNamedValue[] }) {
  return <ul className="quest-codex__list space-y-2">{values.map((value, index) => <li key={`${value.name}-${index}`} className="quest-codex__list-item rounded-lg border px-3 py-2 text-sm">{value.name}</li>)}</ul>;
}

function QuestFact({ label, value }: { label: ReactNode; value: ReactNode }) {
  return <div className="quest-codex__fact rounded-xl border p-4"><dt className="text-xs font-semibold uppercase tracking-wide">{label}</dt><dd className="mt-1 text-lg font-bold">{value}</dd></div>;
}

function QuestFacts({ children }: { children: ReactNode }) {
  return <dl className="quest-codex__facts grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</dl>;
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
    return <li key={normalized} className="text-sm">{resolved
      ? <RichEntityLink target={{ canonicalName: resolved.target_name, entityType: entity, detailRoute: `/${entity === 'npc' ? 'npcs' : 'locations'}/${resolved.target_slug}` }} linkState={linkState} />
      : <div className="quest-codex__reference flex min-h-11 items-center rounded-lg border px-3 py-2">{value.name}</div>}
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
        if (data.slug && data.slug !== questId) {
          navigate(`/quests/${data.slug}${location.search}${location.hash}`, { replace: true, state: location.state });
        }
        if (isAuthenticated && data.id) void activityApi.record({ activity_type: 'view_quest', entity_type: 'quest', entity_id: String(data.id), metadata: { name: data.name } }).catch(() => undefined);
      } catch {
        setError(t('questDetail.notFound'));
      } finally { setLoading(false); }
    };
    void run();
    return () => controller.abort();
  }, [questId, isAuthenticated, location.hash, location.search, location.state, navigate, t]);

  useEffect(() => {
    if (!quest || !location.hash) return undefined;
    const targetId = decodeURIComponent(location.hash.slice(1));
    const timer = window.setTimeout(() => {
      const target = document.getElementById(targetId);
      target?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'start',
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [location.hash, quest]);

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
    ['locations', t('questDetail.locations')],
  ];
  const relationshipReferences = quest.relationships.filter(relationship => !relationship.mission_id);
  const hasDetails = hasDetailedQuestData(quest);

  return <Page><div>
    <button onClick={() => navigate(backTarget)} className="mb-6 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft size={18} />{t('questDetail.back')}</button>
    <article className="quest-codex relative overflow-visible rounded-2xl border shadow-sm">
      <div className="quest-codex__binding" />
      <div className="quest-codex__pages p-5 sm:p-8 lg:p-10">
        <header id="overview" className="quest-codex__title scroll-mt-24 text-center">
          <ScrollText className="mx-auto" size={38} />
          <p className="mt-3 text-xs font-bold uppercase tracking-[0.25em]">{t('questDetail.codexEntry')}</p>
          <h1 className="mx-auto mt-3 max-w-4xl font-serif text-3xl font-bold sm:text-5xl">{quest.name}</h1>
          {quest.group_name && <p className="mt-3 text-sm font-semibold">{t('questDetail.group', { name: quest.group_name })}</p>}
          <p className="mx-auto mt-6 max-w-3xl text-left text-lg leading-8 sm:text-center">{quest.summary || quest.description || t('questDetail.noDetails')}</p>
        </header>

        <div className="quest-codex__mobile-sticky-title" aria-label={quest.name}>
          <BookOpen className="size-4 shrink-0" />
          <span className="truncate font-semibold">{quest.name}</span>
        </div>

        {!hasDetails ? <div className="quest-codex__empty mx-auto mt-6 max-w-3xl rounded-xl border border-dashed p-4 text-sm"><strong>{t('questDetail.noDetailedData')}</strong><p className="mt-1">{t('questDetail.noDetailedDataHelp')}</p></div> : null}

        <QuestCompletionControl questId={quest.id} questSlug={quest.slug} />

        <div className="mt-8">
          <QuestFacts>
            <QuestFact label={t('questDetail.minimumLevel')} value={quest.min_level ?? t('questDetail.notAvailable')} />
            <QuestFact label={t('questDetail.experience')} value={quest.experience_reward?.toLocaleString() ?? t('questDetail.notAvailable')} />
            <QuestFact label={t('questDetail.premium')} value={quest.premium_required == null ? t('questDetail.unknown') : t(quest.premium_required ? 'questDetail.yes' : 'questDetail.no')} />
            <QuestFact label={t('questDetail.repeatable')} value={quest.repeatable == null ? t('questDetail.unknown') : t(quest.repeatable ? 'questDetail.yes' : 'questDetail.no')} />
          </QuestFacts>
        </div>

        <nav aria-label={t('questDetail.contents')} className="quest-codex__contents my-8 rounded-xl border p-4 sm:p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><BookOpen size={17} />{t('questDetail.contents')}</div>
          <ol className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">{sections.map(([id, label], index) => <li key={id}><a href={`#${id}`} className="quest-codex__toc-link flex min-h-12 items-center gap-3 rounded-lg border px-3 py-2"><span className="font-serif text-base font-bold">{index + 1}</span><span>{label}</span></a></li>)}</ol>
        </nav>

        <div className="quest-codex__spread grid gap-6 lg:grid-cols-2">
          <KnowledgeSection id="requirements" title={t('questDetail.requirements', { count: requirementCount })} icon={<ShieldCheck size={20} />}>
            <div className="space-y-5">
              {quest.required_items.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">{t('questDetail.items')}</h3><div className="space-y-2">{quest.required_items.map((item, index) => <QuestReference key={`${item.name}-${index}`} value={item} kind="item" relationships={relationshipReferences} linkState={cyclopediaState} />)}</div></div>}
              {quest.required_quests.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">{t('questDetail.quests')}</h3><div className="space-y-2">{quest.required_quests.map((requiredQuest, index) => <QuestReference key={`${requiredQuest.name}-${index}`} value={requiredQuest} kind="quest" relationships={relationshipReferences} linkState={cyclopediaState} />)}</div></div>}
              {requirementCount === 0 && <KnowledgeEmpty>{t('questDetail.noRequirements')}</KnowledgeEmpty>}
            </div>
          </KnowledgeSection>
          <KnowledgeSection id="rewards" title={t('questDetail.rewards', { count: quest.rewarded_items.length })} icon={<Gift size={20} />}>
            {quest.rewarded_items.length ? <div className="space-y-2">{quest.rewarded_items.map((item, index) => <QuestReference key={`${item.name}-${index}`} value={item} kind="item" relationships={relationshipReferences} linkState={cyclopediaState} />)}</div> : <KnowledgeEmpty>{t('questDetail.noRewards')}</KnowledgeEmpty>}
          </KnowledgeSection>
        </div>

        <KnowledgeSection id="missions" className="mt-6" title={t('questDetail.missions', { count: quest.missions.length })} icon={<ListOrdered size={20} />}>
          <div className="space-y-6">{quest.missions.length ? quest.missions.map(mission => {
            const missionRelationships = quest.relationships.filter(relationship => relationship.mission_id === mission.id);
            return <article id={`mission-${mission.id}`} key={mission.id} className="quest-codex__mission relative scroll-mt-28 pl-11">
              <div className="quest-codex__mission-marker absolute left-0 top-0 grid size-8 place-items-center rounded-full border text-sm font-bold">{mission.sequence}</div>
              <p className="text-xs font-semibold uppercase tracking-wide">{t('questDetail.chapter', { number: mission.sequence })}</p>
              <h3 className="mt-1 font-serif text-xl font-bold">{mission.title}</h3>
              {mission.description && <p className="mt-3 whitespace-pre-line text-sm leading-7">{mission.description}</p>}
              {mission.objectives.length > 0 && <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{mission.objectives.map((value, index) => <li key={index}>{value}</li>)}</ul>}
              {(mission.required_items.length > 0 || mission.rewarded_items.length > 0) ? <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {mission.required_items.length > 0 ? <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">{t('questEnhancement.requirementItems')}</h4><div className="space-y-2">{mission.required_items.map((item, index) => <QuestReference key={`${item.name}-${index}`} value={item} kind="item" relationships={missionRelationships} linkState={cyclopediaState} compact />)}</div></div> : null}
                {mission.rewarded_items.length > 0 ? <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">{t('questEnhancement.rewardItems')}</h4><div className="space-y-2">{mission.rewarded_items.map((item, index) => <QuestReference key={`${item.name}-${index}`} value={item} kind="item" relationships={missionRelationships} linkState={cyclopediaState} compact />)}</div></div> : null}
              </div> : null}
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {mission.related_npcs.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">{t('questDetail.npcs')}</h4><EntityReferences values={mission.related_npcs} relationships={missionRelationships} entity="npc" linkState={cyclopediaState} /></div>}
                {mission.locations.length > 0 && <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">{t('questDetail.locations')}</h4><EntityReferences values={mission.locations} relationships={missionRelationships} entity="location" linkState={cyclopediaState} /></div>}
              </div>
            </article>;
          }) : <KnowledgeEmpty>{t('questDetail.noMissions')}</KnowledgeEmpty>}</div>
        </KnowledgeSection>

        <KnowledgeSection id="locations" className="mt-6" title={t('questDetail.locations')} icon={<MapPin size={20} />}>
          <div className="grid gap-5 lg:grid-cols-[minmax(14rem,2fr)_minmax(18rem,3fr)]">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1">
              <section className="quest-codex__subsection rounded-xl border p-4">
                <h3 className="mb-3 flex items-center gap-2 font-semibold"><UserRound size={16} />{t('questDetail.npcs')}</h3>
                {quest.starting_npcs.length > 0 || quest.related_npcs.length > 0
                  ? <EntityReferences values={[...quest.starting_npcs, ...quest.related_npcs]} relationships={relationshipReferences} entity="npc" linkState={cyclopediaState} />
                  : <KnowledgeEmpty>{t('questDetail.noDetails')}</KnowledgeEmpty>}
              </section>
              <section className="quest-codex__subsection rounded-xl border p-4">
                <h3 className="mb-3 flex items-center gap-2 font-semibold"><MapPin size={16} />{t('questDetail.locations')}</h3>
                {quest.locations.length > 0
                  ? <EntityReferences values={quest.locations} relationships={relationshipReferences} entity="location" linkState={cyclopediaState} />
                  : <KnowledgeEmpty>{t('questDetail.noDetails')}</KnowledgeEmpty>}
              </section>
            </div>
            <section className="quest-codex__subsection rounded-xl border p-4">
              <h3 className="mb-1 flex items-center gap-2 font-semibold"><MapPin size={16} />{t('questDetail.mapLocations')}</h3>
              <p className="mb-3 text-sm">{t('questDetail.mapLocationsHelp')}</p>
              <QuestMapInsets entityId={quest.knowledge_entity_id} questName={quest.name} questSlug={quest.slug || String(quest.id)} />
            </section>
          </div>
        </KnowledgeSection>

        {quest.access_unlocks.length > 0 && <KnowledgeSection className="mt-6" title={t('questDetail.access')}><Names values={quest.access_unlocks} /></KnowledgeSection>}
        <section className="quest-codex__section mt-6 rounded-2xl border p-5 sm:p-6">
          <h2 className="mb-4 font-serif text-xl font-bold sm:text-2xl">{t('questDetail.creatures')}</h2>
          {quest.related_creatures.length ? <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{quest.related_creatures.map(creature => <div key={creature.creature_id} className="relative">{creature.is_boss ? <Crown size={14} className="absolute left-3 top-3 z-10 text-danger" /> : null}<RichEntityLink target={{ canonicalName: creature.creature_name, entityType: 'creature', detailRoute: `/creatures/${creature.creature_slug || creature.creature_id}`, imageUrl: `/api/v1/creatures/${creature.creature_id}/image`, summary: creature.classification || undefined }} linkState={cyclopediaState} /></div>)}</div> : <KnowledgeEmpty>{t('questDetail.noCreatures')}</KnowledgeEmpty>}
        </section>
        <footer className="mt-6 flex flex-wrap items-center gap-3 border-t pt-4 text-xs">{quest.last_synced_at && <span>{t('questDetail.updated', { date: new Date(quest.last_synced_at).toLocaleString() })}</span>}{quest.source_url && <a href={quest.source_url} target="_blank" rel="noreferrer" className="hover:underline">{t('questDetail.source')}</a>}</footer>
        <div className="mt-5 flex justify-end"><SuggestCorrectionLink entityType="Quest" entityName={quest.name} /></div>
      </div>
    </article>
  </div></Page>;
}
