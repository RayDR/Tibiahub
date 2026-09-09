import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownAZ,
  ArrowRight,
  ArrowUpAZ,
  Crown,
  Library,
  Loader2,
  MapPin,
  Repeat2,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  questBrowserApi,
  type QuestBrowseResult,
  type QuestBrowseSort,
  type QuestFacets,
} from '../services/questBrowser';
import { hasDetailedQuestSummary } from '../utils/questPresentation';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import { useCyclopediaPreviewSelection } from './cyclopedia/CyclopediaPreviewSelectionContext';

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

function questIdentifier(quest: QuestBrowseResult): string {
  return String(quest.slug || quest.id || quest.external_id || quest.name);
}

export default function QuestLibraryShelves({ linkState, onNavigate }: Props) {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const preview = useCyclopediaPreviewSelection();
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
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const activeBrowseRef = useRef<AbortController | null>(null);
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

  useEffect(() => () => activeBrowseRef.current?.abort(), []);

  const load = useCallback(async (reset: boolean) => {
    if (query.length === 1) {
      activeBrowseRef.current?.abort();
      setQuests([]);
      setSkip(0);
      setHasMore(false);
      setLoading(false);
      setLoadingMore(false);
      loadingMoreRef.current = false;
      return;
    }
    if (!reset && loadingMoreRef.current) return;

    const controller = new AbortController();
    if (reset) {
      activeBrowseRef.current?.abort();
      setLoading(true);
      setLoadingMore(false);
      loadingMoreRef.current = false;
    } else {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    activeBrowseRef.current = controller;

    const nextSkip = reset ? 0 : skip;
    setError(false);
    try {
      const rows = await questBrowserApi.browse({
        search: query.length > 1 ? query : undefined,
        access_only: accessOnly,
        sort_by: sortBy,
        sort_order: sortOrder,
        skip: nextSkip,
        limit: PAGE_SIZE,
      }, controller.signal);
      if (controller.signal.aborted) return;

      setQuests((current) => {
        if (reset) return rows;
        const seen = new Set(current.map(questKey));
        return [...current, ...rows.filter((row) => !seen.has(questKey(row)))];
      });
      setSkip(nextSkip + rows.length);
      setHasMore(rows.length === PAGE_SIZE);
    } catch {
      if (controller.signal.aborted) return;
      if (reset) setQuests([]);
      setError(true);
    } finally {
      if (activeBrowseRef.current === controller) {
        setLoading(false);
        setLoadingMore(false);
        loadingMoreRef.current = false;
      }
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
  const countIsPartial = Boolean(query && hasMore);
  const selectedIdentifier = preview.selection?.kind === 'quest' ? preview.selection.identifier : null;

  return (
    <section aria-label={t('cyclopedia.discovery.questLibrary')} className="cyclopedia-quest-browser space-y-4">
      <div className="cyclopedia-quest-toolbar rounded-2xl border border-line bg-surface-raised/70 p-3 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <Library className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="font-serif text-lg font-semibold text-content-primary">{t('cyclopedia.discovery.questLibrary')}</h2>
              <p className="text-xs text-content-muted">{t('cyclopedia.filters.resultCount', { count: visibleCount })}{countIsPartial ? ' +' : ''}</p>
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

      {loading ? (
        <div className="flex min-h-44 items-center justify-center text-primary"><Loader2 className="size-7 animate-spin" /></div>
      ) : error ? (
        <div className="rounded-xl border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
          <button type="button" className="font-semibold hover:underline" onClick={() => void load(true)}>{t('common.retry')}</button>
        </div>
      ) : quests.length ? (
        <>
          <div className="cyclopedia-quest-grid grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {quests.map((quest) => {
              const identifier = questIdentifier(quest);
              const active = selectedIdentifier === identifier;
              const type = quest.quest_type || quest.category || quest.group_name || 'Quest';
              const location = quest.location;
              const npc = quest.npc;
              return (
                <article
                  data-cyclopedia-result
                  data-cyclopedia-quest-card="true"
                  data-quest-identifier={identifier}
                  data-selected={active ? 'true' : 'false'}
                  key={questKey(quest)}
                  role="button"
                  tabIndex={0}
                  aria-pressed={active}
                  onClick={() => preview.select({ kind: 'quest', identifier })}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      preview.select({ kind: 'quest', identifier });
                    }
                  }}
                  className="cyclopedia-quest-card group"
                >
                  <span className="quest-card-corner"><BrandCategoryFallbackIcon category="quests" className="size-4" /></span>
                  <Link
                    to={`/quests/${identifier}`}
                    state={linkState}
                    onClick={(event) => {
                      event.stopPropagation();
                      onNavigate?.();
                    }}
                    className="quest-card-open"
                    aria-label={t('questDetail.openQuest')}
                    title={t('questDetail.openQuest')}
                  >
                    <ArrowRight className="size-4" />
                  </Link>

                  <div className="quest-card-art" aria-hidden="true">
                    <BrandCategoryFallbackIcon category="quests" className="quest-card-art-icon" />
                  </div>

                  <div className="quest-card-body">
                    <div className="flex min-w-0 items-start gap-2">
                      <h3 className="min-w-0 flex-1 line-clamp-2 font-serif text-lg font-semibold text-content-primary">{quest.name}</h3>
                      {quest.is_access_quest ? <span className="quest-card-badge quest-card-badge-access">{t('questDetail.access')}</span> : null}
                    </div>

                    <div className="quest-card-stats">
                      <QuestStat label={t('questDetail.minimumLevel')} value={quest.min_level?.toLocaleString() || '—'} />
                      <QuestStat label={t('questDetail.experience')} value={quest.experience_reward?.toLocaleString() || '—'} />
                      <QuestStat label="Type" value={type} />
                    </div>

                    <div className="quest-card-meta">
                      {location ? <span><MapPin className="size-4 shrink-0 text-primary" /><span className="truncate">{location}</span></span> : null}
                      {npc ? <span><UserRound className="size-4 shrink-0 text-content-muted" /><span className="truncate">{npc}</span></span> : null}
                    </div>

                    <p className="quest-card-summary">
                      {quest.description || (hasDetailedQuestSummary(quest) ? type : t('questDetail.noDetailedData'))}
                    </p>

                    <div className="quest-card-flags">
                      {quest.premium_required ? <span><Crown className="size-3.5" />{t('questDetail.premium')}</span> : null}
                      {quest.repeatable ? <span><Repeat2 className="size-3.5" />{t('questDetail.repeatable')}</span> : null}
                      {quest.is_access_quest ? <span><ShieldCheck className="size-3.5" />{t('questDetail.access')}</span> : null}
                      {!quest.premium_required && !quest.repeatable && !quest.is_access_quest ? <span className="text-content-muted">{type}</span> : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          {hasMore ? <div ref={sentinelRef} className="h-px w-full" aria-hidden="true" /> : null}
          {loadingMore ? <div className="flex items-center justify-center gap-2 py-4 text-xs text-content-muted"><Loader2 className="size-4 animate-spin text-primary" />{t('common.loading')}</div> : null}
        </>
      ) : (
        <div className="rounded-xl border border-line bg-surface-base/40 p-8 text-center text-sm text-content-muted">{t('cyclopedia.quests.noDetails')}</div>
      )}
    </section>
  );
}

function QuestStat({ label, value }: { label: string; value: string }) {
  return <div className="quest-card-stat"><span>{label}</span><strong title={value}>{value}</strong></div>;
}
