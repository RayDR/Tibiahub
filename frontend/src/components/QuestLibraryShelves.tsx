import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Clock3, Flame, Library } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../context/AuthContext';
import { activityApi, type UserActivityEntry } from '../services/activity';
import { questsApi } from '../services/api';
import type { QuestSearchResult } from '../types';
import KnowledgeCategoryMedia from './knowledge/KnowledgeCategoryIcon';

interface Props {
  linkState?: unknown;
  onNavigate?: () => void;
}

interface QuestCard {
  id: string;
  name: string;
  slug?: string;
  subtitle?: string;
}

const keyFor = (item: QuestCard) => (item.slug || item.name).trim().toLocaleLowerCase();

function fromQuest(row: QuestSearchResult): QuestCard {
  return {
    id: String(row.id || row.slug || row.name),
    name: row.name,
    slug: row.slug,
    subtitle: row.group_name || row.location || undefined,
  };
}

function fromActivity(row: UserActivityEntry): QuestCard | null {
  const name = String(row.metadata?.name || '').trim();
  if (row.activity_type !== 'view_quest' || !name || !row.entity_id) return null;
  return {
    id: String(row.entity_id),
    name,
    slug: String(row.metadata?.slug || '').trim() || undefined,
  };
}

function unique(items: QuestCard[], used: Set<string>, limit: number): QuestCard[] {
  const result: QuestCard[] = [];
  for (const item of items) {
    const key = keyFor(item);
    if (!key || used.has(key)) continue;
    used.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

export default function QuestLibraryShelves({ linkState, onNavigate }: Props) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [popular, setPopular] = useState<QuestCard[]>([]);
  const [trending, setTrending] = useState<QuestCard[]>([]);
  const [fallback, setFallback] = useState<QuestCard[]>([]);
  const [history, setHistory] = useState<QuestCard[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      questsApi.getPopular(20, controller.signal),
      questsApi.list({ limit: 40 }, controller.signal),
      questsApi.getTrending(20, controller.signal),
    ]).then(([popularRows, fallbackRows, trendingRows]) => {
      if (controller.signal.aborted) return;
      setPopular(popularRows.map(fromQuest));
      setFallback(fallbackRows.map(fromQuest));
      setTrending(trendingRows.map(fromQuest));
    }).catch(() => undefined);

    if (isAuthenticated) {
      void activityApi.getMine(80, controller.signal).then((rows) => {
        if (!controller.signal.aborted) setHistory(rows.map(fromActivity).filter((row): row is QuestCard => Boolean(row)));
      }).catch(() => setHistory([]));
    } else {
      setHistory([]);
    }
    return () => controller.abort();
  }, [isAuthenticated]);

  const shelves = useMemo(() => {
    const used = new Set<string>();
    const allTime = unique(popular, used, 8);
    const personal = unique([...(history.length ? history : fallback), ...fallback], used, 8);
    const recent = unique([...trending, ...fallback], used, 8);
    return { personal, allTime, recent };
  }, [fallback, history, popular, trending]);

  if (!shelves.personal.length && !shelves.allTime.length && !shelves.recent.length) return null;

  return (
    <section aria-label={t('cyclopedia.discovery.questLibrary')} className="rounded-3xl border border-line bg-surface-raised/80 p-4 shadow-sm sm:p-6">
      <div className="mb-5 flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"><Library className="size-5" /></span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{t('nav.quests')}</p>
          <h2 className="text-xl font-semibold text-content-primary">{t('cyclopedia.discovery.questLibrary')}</h2>
        </div>
      </div>
      <div className="space-y-4">
        <QuestShelf title={t('cyclopedia.discovery.allTimePopular')} icon={BookOpen} items={shelves.allTime} horizontal linkState={linkState} onNavigate={onNavigate} />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(16rem,3fr)] lg:items-start">
          <QuestShelf title={history.length ? t('cyclopedia.discovery.forYou') : t('cyclopedia.discovery.libraryPicks')} icon={Library} items={shelves.personal} featured horizontal linkState={linkState} onNavigate={onNavigate} />
          <QuestShelf title={t('cyclopedia.discovery.questTrends')} icon={history.length ? Clock3 : Flame} items={shelves.recent} linkState={linkState} onNavigate={onNavigate} />
        </div>
      </div>
    </section>
  );
}

function QuestShelf({ title, icon: Icon, items, featured = false, horizontal = false, linkState, onNavigate }: {
  title: string;
  icon: typeof BookOpen;
  items: QuestCard[];
  featured?: boolean;
  horizontal?: boolean;
  linkState?: unknown;
  onNavigate?: () => void;
}) {
  if (!items.length) return null;
  return <article className={`relative min-w-0 overflow-hidden rounded-2xl border p-4 after:absolute after:inset-x-3 after:bottom-2 after:h-1 after:rounded-full after:bg-gradient-to-r after:from-primary-active/50 after:via-primary/35 after:to-primary-active/50 ${featured ? 'border-primary/25 bg-primary/[0.045] lg:p-5' : 'border-line bg-surface-base/50'}`}>
    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-content-primary"><Icon className="size-4 text-primary" />{title}</h3>
    <div className={`flex snap-x gap-2 overflow-x-auto overscroll-x-contain pb-3 [scrollbar-width:thin] ${horizontal ? '' : 'lg:grid lg:max-h-[23rem] lg:overflow-y-auto lg:overflow-x-hidden'}`}>
      {items.map((item, index) => <Link key={keyFor(item)} to={`/quests/${item.slug || item.id}`} state={linkState} onClick={() => onNavigate?.()} className={`group flex shrink-0 snap-start items-center gap-3 rounded-r-xl rounded-l-sm border border-line border-l-4 bg-surface-raised p-3 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:bg-surface-active ${featured ? 'w-[16rem]' : 'w-[13rem]'} ${!horizontal ? 'lg:w-auto' : ''} ${index % 3 === 0 ? 'border-l-primary-active/55' : index % 3 === 1 ? 'border-l-primary/45' : 'border-l-accent/45'}`}>
        <KnowledgeCategoryMedia category="quests" label={item.name} className={featured ? 'size-14' : 'size-11'} mediaClassName={featured ? 'size-13 p-0.5' : 'size-10 p-0.5'} />
        <span className="min-w-0"><strong className="line-clamp-2 text-sm text-content-primary">{item.name}</strong>{item.subtitle ? <small className="mt-1 block truncate text-xs text-content-muted">{item.subtitle}</small> : null}</span>
      </Link>)}
    </div>
  </article>;
}
