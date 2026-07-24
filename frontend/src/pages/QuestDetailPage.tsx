import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Crown, Loader2, MapPin, ScrollText, UserRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { questsApi } from '../services/api';
import type { QuestDetail, QuestItemValue, QuestNamedValue } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';

function Names({ values }: { values: QuestNamedValue[] }) {
  return <ul className="space-y-2">{values.map((value, index) => <li key={`${value.name}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">{value.name}</li>)}</ul>;
}

function Items({ values }: { values: QuestItemValue[] }) {
  return <ul className="space-y-2">{values.map((value, index) => <li key={`${value.name}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">{value.amount > 1 ? `${value.amount}× ` : ''}{value.name}{value.note ? ` — ${value.note}` : ''}</li>)}</ul>;
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
  if (loading) return <div className="flex min-h-screen items-center justify-center text-amber-500"><Loader2 className="animate-spin" size={42} /></div>;
  if (!quest || error) return <div className="mx-auto mt-20 max-w-3xl rounded-2xl border border-red-500/20 bg-red-950/20 p-6 text-red-100"><div className="mb-3 text-lg font-semibold">{t('questDetail.unavailable')}</div><p className="text-sm text-red-200/80">{error || t('questDetail.notFound')}</p></div>;

  const requirementCount = quest.required_items.length + quest.required_quests.length;
  return <div className="min-h-screen pb-20 pt-28"><div className="container mx-auto px-4">
    <button onClick={() => navigate('/cyclopedia')} className="mb-6 flex min-h-11 items-center gap-2 text-slate-400 hover:text-white"><ArrowLeft size={18} />{t('questDetail.back')}</button>
    <article className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4 sm:p-6">
      <header className="mb-5"><div className="flex items-start gap-3 text-amber-300"><ScrollText className="mt-1 shrink-0" size={24} /><div><h1 className="text-2xl font-bold text-white sm:text-3xl">{quest.name}</h1>{quest.group_name && <p className="mt-1 text-xs text-amber-200">{t('questDetail.group', { name: quest.group_name })}</p>}</div></div><p className="mt-4 text-slate-300">{quest.summary || quest.description || t('questDetail.noDetails')}</p></header>
      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
        <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">{t('questDetail.minimumLevel')}: {quest.min_level ?? t('questDetail.notAvailable')}</div>
        <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">{t('questDetail.experience')}: {quest.experience_reward ?? t('questDetail.notAvailable')}</div>
        <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">{t('questDetail.premium')}: {quest.premium_required == null ? t('questDetail.unknown') : t(quest.premium_required ? 'questDetail.yes' : 'questDetail.no')}</div>
        <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">{t('questDetail.repeatable')}: {quest.repeatable == null ? t('questDetail.unknown') : t(quest.repeatable ? 'questDetail.yes' : 'questDetail.no')}</div>
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <details open className="rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer font-semibold text-amber-200">{t('questDetail.requirements', { count: requirementCount })}</summary><div className="mt-3 space-y-4">{quest.required_items.length > 0 && <div><h3 className="mb-2 text-sm text-slate-400">{t('questDetail.items')}</h3><Items values={quest.required_items} /></div>}{quest.required_quests.length > 0 && <div><h3 className="mb-2 text-sm text-slate-400">{t('questDetail.quests')}</h3><Names values={quest.required_quests} /></div>}{requirementCount === 0 && <p className="text-sm text-slate-500">{t('questDetail.noRequirements')}</p>}</div></details>
        <details open className="rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer font-semibold text-amber-200">{t('questDetail.rewards', { count: quest.rewarded_items.length })}</summary><div className="mt-3">{quest.rewarded_items.length ? <Items values={quest.rewarded_items} /> : <p className="text-sm text-slate-500">{t('questDetail.noRewards')}</p>}</div></details>
      </div>
      <details open className="mt-6 rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer font-semibold text-amber-200">{t('questDetail.missions', { count: quest.missions.length })}</summary><div className="mt-3 space-y-3">{quest.missions.length ? quest.missions.map(mission => <article key={mission.id} className="rounded-lg bg-slate-950/60 p-4"><h3 className="font-semibold text-slate-100">{mission.sequence}. {mission.title}</h3>{mission.description && <p className="mt-2 text-sm text-slate-300">{mission.description}</p>}{mission.objectives.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-400">{mission.objectives.map((value, index) => <li key={index}>{value}</li>)}</ul>}</article>) : <p className="text-sm text-slate-500">{t('questDetail.noMissions')}</p>}</div></details>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {(quest.starting_npcs.length > 0 || quest.related_npcs.length > 0) && <section className="rounded-xl border border-slate-800 p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-amber-200"><UserRound size={16} />{t('questDetail.npcs')}</h2><Names values={[...quest.starting_npcs, ...quest.related_npcs]} /></section>}
        {quest.locations.length > 0 && <section className="rounded-xl border border-slate-800 p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-amber-200"><MapPin size={16} />{t('questDetail.locations')}</h2><Names values={quest.locations} /></section>}
      </div>
      {quest.access_unlocks.length > 0 && <details className="mt-6 rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer font-semibold text-amber-200">{t('questDetail.access')}</summary><div className="mt-3"><Names values={quest.access_unlocks} /></div></details>}
      <section className="mt-6"><h2 className="mb-2 text-lg font-semibold text-amber-200">{t('questDetail.creatures')}</h2>{quest.related_creatures.length ? <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{quest.related_creatures.map(creature => <Link to={`/creatures/${creature.creature_slug || creature.creature_id}`} key={creature.creature_id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 hover:border-amber-500/40"><div className="flex items-center gap-2 text-slate-100">{creature.is_boss && <Crown size={14} className="text-red-300" />}<span className="font-semibold">{creature.creature_name}</span></div><div className="mt-1 text-xs text-slate-400">{creature.classification || t('questDetail.unknownClassification')}</div></Link>)}</div> : <p className="text-sm text-slate-500">{t('questDetail.noCreatures')}</p>}</section>
      <footer className="mt-6 flex flex-wrap items-center gap-3 text-xs text-slate-500">{quest.last_synced_at && <span>{t('questDetail.updated', { date: new Date(quest.last_synced_at).toLocaleString() })}</span>}{unresolved > 0 && <span>{t('questDetail.referencesPending', { count: unresolved })}</span>}{quest.source_url && <a href={quest.source_url} target="_blank" rel="noreferrer" className="text-amber-400 hover:text-amber-300">{t('questDetail.source')}</a>}</footer>
    </article>
  </div></div>;
}
