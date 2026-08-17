import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDownAZ, ArrowUpAZ, BookOpen, Library, Loader2, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  questBrowserApi,
  type QuestBrowseResult,
  type QuestBrowseSort,
  type QuestFacets,
} from '../services/questBrowser';

interface Props {
  linkState?: unknown;
  onNavigate?: () => void;
}

type SortOrder = 'asc' | 'desc';

const PAGE_SIZE = 24;
const FILTER_STORAGE_KEY = 'tibiahub:cyclopedia:quest-library';

interface StoredFilters {
  accessOnly?: boolean;
  sortBy?: QuestBrowseSort;
  sortOrder?: SortOrder;
}

function loadStoredFilters(): StoredFilters {
  try {
    const value = sessionStorage.getItem(FILTER_STORAGE_KEY);
    return value ? JSON.parse(value) as StoredFilters : {};
  } catch {
    return {};
  }
}

function questKey(quest: QuestBrowseResult): string {
  return String(quest.id || quest.slug || quest.external_id || quest.name);
}

export default function QuestLibraryShelves({ linkState, onNavigate }: Props) {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const query = (searchParams.get('q') || '').trim();
  const stored = useMemo(loadStoredFilters, []);
  const [accessOnly, setAccessOnly] = useState(Boolean(stored.accessOnly));
  const [sortBy, setSortBy] = useState<QuestBrowseSort>(stored.sortBy === 'min_level' ? 'min_level' : 'name');
  const [sortOrder, setSortOrder] = useState<SortOrder>(stored.sortOrder === 'desc' ? 'desc' : 'asc');
  const [facets, setFacets] = useState<QuestFacets>({
    total: 0,
    access_quests: 0,
    minimum_level_known: 0,
    minimum_level_min: null,
    minimum_level_max: null,
  });
  const [quests, setQuests] = useState<QuestBrowseResult[]>([]);
  const [selected, setSelected] = useState<QuestBrowseResult | null>(null);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);

  useEffect(() => {
    try {
      sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({ accessOnly, sortBy, sortOrder }));
    } catch {
      // Session storage is optional.
    }
  }, [accessOnly, sortBy, sortOrder]);

  useEffect(() => {
    const controller = new AbortController();
    void questBrowserApi.getFacets(controller.signal).then((value) => {
      if (!controller.signal.aborted) setFacets(value);
    }).catch(() => undefined);
    return () => controller.abort();
  }, []);

  const load = useCallback(async (reset: boolean) => {
    if (query.length === 1) {
      setQuests([]);
      setSelected(null);
      setSkip(0);
      setHasMore(false);
      setLoading(false);
      setLoadingMore(false);
      return;
    }
    if (!reset && loadingMoreRef.current) return;
    const nextSkip = reset ? 0 : skip;
    if (reset) setLoading(true);
    else {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    setError(false);
    try {
      const rows = await questBrowserApi.browse({
        search: query.length > 1 ? query : undefined,
        access_only: accessOnly,
        sort_by: sortBy,
        sort_order: sortOrder,
        skip: nextSkip,
        limit: PAGE_SIZE,
      });
      setQuests((current) => {
        if (reset) return rows;
        const seen = new Set(current.map(questKey));
        return [...current, ...rows.filter((row) => !seen.has(questKey(row)))];
      });
      setSkip(nextSkip + rows.length);
      setHasMore(rows.length === PAGE_SIZE);
      if (reset) {
        setSelected((current) => current && rows.some((row) => questKey(row) === questKey(current)) ? current : null);
      }
    } catch {
      if (reset) setQuests([]);
      setError(true);
    } finally {
      setLoading(false);
      setLoadingMore(false);
      loadingMoreRef.current = false;
    }
  }, [accessOnly, query, skip, sortBy, sortOrder]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(true), 250);
    return () => window.clearTimeout(timer);
  }, [accessOnly, query, sortBy, sortOrder]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading || loadingMore || error) return undefined;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !loadingMoreRef.current) void load(false);
    }, { rootMargin: '0px 0px 600px 0px', threshold: 0 });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [error, hasMore, load, loading, loadingMore, quests.length]);

  const visibleCount = !query
    ? accessOnly ? facets.access_quests : facets.total
    : quests.length;

  return (
    <section aria-label={t('cyclopedia.discovery.questLibrary')} className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface-raised/70 p-3 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <Library className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="font-serif text-lg font-semibold text-content-primary">{t('cyclopedia.discovery.questLibrary')}</h2>
              <p className="text-xs text-content-muted">{t('cyclopedia.filters.resultCount', { count: visibleCount })}</p>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-[auto_minmax(10rem,14rem)_auto]">
            <button
              type="button"
              aria-pressed={accessOnly}
              onClick={() => setAccessOnly((value) => !value)}
              className={`app-button-ghost min-h-10 justify-center gap-2 px-3 text-xs ${accessOnly ? 'border-primary/40 bg-primary/10 text-primary' : ''}`}
            >
              <ShieldCheck className="size-4" />
              {t('questDetail.access')} ({facets.access_quests.toLocaleString()})
            </button>

            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as QuestBrowseSort)} className="app-input min-h-10 text-sm">
              <option value="name">{t('cyclopedia.sort.name')}</option>
              <option value="min_level">{t('questDetail.minimumLevel')}</option>
            </select>

            <button
              type="button"
              onClick={() => setSortOrder((value) => value === 'asc' ? 'desc' : 'asc')}
              className="app-button-ghost min-h-10 justify-center gap-2 px-3 text-xs"
            >
              {sortOrder === 'asc' ? <ArrowDownAZ className="size-4" /> : <ArrowUpAZ className="size-4" />}
              {sortOrder === 'asc' ? t('cyclopedia.sort.ascending') : t('cyclopedia.sort.descending')}
            </button>
          </div>
        </div>
      </div>

      {selected ? (
        <article className="relative overflow-hidden rounded-2xl border border-primary/25 bg-surface-base shadow-sm">
          <div className="grid md:grid-cols-2">
            <div className="relative border-b border-line p-5 md:border-b-0 md:border-r sm:p-6">
              <div className="absolute inset-y-3 right-0 w-px bg-line/80" aria-hidden="true" />
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">{t('questDetail.codexEntry')}</p>
              <h3 className="mt-2 font-serif text-2xl font-bold text-content-primary">{selected.name}</h3>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                {selected.min_level != null ? <span className="rounded-full border border-line bg-surface-raised px-2.5 py-1 text-content-secondary">{t('questDetail.minimumLevel')}: {selected.min_level}</span> : null}
                {selected.is_access_quest ? <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 font-semibold text-primary">{t('questDetail.access')}</span> : null}
                {selected.premium_required ? <span className="rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-warning">{t('questDetail.premium')}</span> : null}
              </div>
            </div>
            <div className="flex min-h-40 flex-col justify-between p-5 sm:p-6">
              <p className="line-clamp-5 text-sm leading-6 text-content-secondary">{selected.description || t('cyclopedia.quests.noDetails')}</p>
              {(selected.slug || selected.id != null) ? (
                <Link
                  to={`/quests/${selected.slug || selected.id}`}
                  state={linkState}
                  onClick={() => onNavigate?.()}
                  className="mt-4 inline-flex items-center gap-2 self-start text-sm font-semibold text-primary hover:underline"
                >
                  <BookOpen className="size-4" />
                  {t('cyclopedia.quests.openDetail')}
                </Link>
              ) : null}
            </div>
          </div>
        </article>
      ) : null}

      {loading ? (
        <div className="flex min-h-44 items-center justify-center text-primary"><Loader2 className="size-7 animate-spin" /></div>
      ) : error ? (
        <div className="rounded-xl border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
          <button type="button" className="font-semibold hover:underline" onClick={() => void load(true)}>{t('common.retry')}</button>
        </div>
      ) : quests.length ? (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {quests.map((quest) => {
              const active = selected && questKey(selected) === questKey(quest);
              return (
                <button
                  type="button"
                  data-cyclopedia-result
                  key={questKey(quest)}
                  onClick={() => setSelected(quest)}
                  className={`group relative min-h-[5.25rem] overflow-hidden rounded-r-xl rounded-l-sm border border-line border-l-4 bg-surface-raised px-4 py-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/45 ${active ? 'border-l-primary ring-1 ring-primary/30' : quest.is_access_quest ? 'border-l-primary/70' : 'border-l-content-muted/35'}`}
                >
                  <div className="flex h-full items-start gap-3">
                    <BookOpen className="mt-0.5 size-4 shrink-0 text-primary/80" />
                    <div className="min-w-0 flex-1">
                      <strong className="line-clamp-2 text-sm leading-5 text-content-primary">{quest.name}</strong>
                      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-content-muted">
                        <span>{t('questDetail.minimumLevel')}: {quest.min_level ?? '—'}</span>
                        {quest.is_access_quest ? <span className="font-semibold text-primary">{t('questDetail.access')}</span> : null}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          {hasMore ? <div ref={sentinelRef} className="h-px w-full" aria-hidden="true" /> : null}
          {loadingMore ? <div className="flex items-center justify-center gap-2 py-4 text-xs text-content-muted"><Loader2 className="size-4 animate-spin text-primary" />{t('common.loading')}</div> : null}
        </>
      ) : (
        <div className="rounded-xl border border-line bg-surface-base/40 p-8 text-center text-sm text-content-muted">{t('cyclopedia.states.creatureEmptyTitle')}</div>
      )}
    </section>
  );
}
