import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Link,
  useNavigate,
  useSearchParams } from 'react-router-dom';
import { AlertTriangle,
  ArrowDownAZ,
  ArrowUpAZ,
  Loader2,
  Search,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBook, faScroll } from '@fortawesome/free-solid-svg-icons';

import CreatureCard from '../components/CreatureCard';
import HuntZoneCard from '../components/HuntZoneCard';
import ImageWithFallback from '../components/ImageWithFallback';
import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  questsApi,
  type CreatureCategoryPreview,
} from '../services/api';
import {
  itemBrowserApi,
  type ItemBrowseSort,
  type ItemCategoryFacet,
} from '../services/itemBrowser';
import {
  buildCacheKey,
  cacheGet,
  cacheSet,
  loadSnapshot,
  saveSnapshot,
} from '../services/cyclopediaCache';
import { checkAndInvalidateIfStale } from '../services/cyclopediaCache';
import { CreatureSimple, HuntZone, ItemSearchResult, QuestSearchResult } from '../types';
import PageHeader from '../components/ui/PageHeader';
import AppTabs from '../components/ui/AppTabs';
import AppCard from '../components/ui/AppCard';
import { Page } from '../components/ui';
import { cyclopediaSections, modeToTab, tabToMode } from '../config/cyclopediaSections';
import {
  CREATURE_CATEGORIES,
  normalizeCategoryKey,
  normalizeCreatureCategory,
  type CreatureCategory,
} from '../config/creatureCategories';
import { iconByCategory } from '../components/icons/CategoryIcons';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import CyclopediaDiscovery from '../components/CyclopediaDiscovery';
import QuestLibraryShelves from '../components/QuestLibraryShelves';
import CompactEntityStrip from '../components/CompactEntityStrip';
import KnowledgeCategoryIcon from '../components/knowledge/KnowledgeCategoryIcon';
import { KnowledgeBadge } from '../components/knowledge/KnowledgeDetail';
import KnowledgeSearchBox, {
  type KnowledgeSearchSection,
  type KnowledgeSuggestion,
} from '../components/search/KnowledgeSearchBox';
import {
  buildCyclopediaPath,
  createCyclopediaRouteState,
  saveCyclopediaReturnTarget,
} from '../utils/cyclopediaNavigation';

type SearchMode = KnowledgeSearchSection;
type CreatureSort = 'name' | 'experience' | 'hitpoints' | 'difficulty';
type SortOrder = 'asc' | 'desc';
interface CyclopediaPreviewCard {
  id: string;
  name: string;
  subtitle: string;
  to: string;
  imageUrl?: string;
  createdAt?: string;
}

type SelectedSuggestionKind =
  | 'item'
  | 'zone'
  | 'quest';

interface SelectedSuggestion {
  kind: SelectedSuggestionKind;
  query: string;
}

const SELECTED_SEPARATOR = ':';

const encodeSelectedSuggestion = (
  kind: SelectedSuggestionKind,
  query: string,
) => {
  const normalized = query.trim();
  if (!normalized) return '';
  return `${kind}${SELECTED_SEPARATOR}${encodeURIComponent(normalized)}`;
};

const decodeSelectedSuggestion = (
  value: string,
): SelectedSuggestion | null => {
  if (!value) return null;

  const index = value.indexOf(SELECTED_SEPARATOR);
  if (index <= 0) return null;

  const kind = value.slice(0, index) as SelectedSuggestionKind;
  const raw = value.slice(index + 1);

  if (!['item', 'zone', 'quest'].includes(kind)) {
    return null;
  }

  try {
    const query = decodeURIComponent(raw).trim();
    if (!query) return null;
    return {
      kind,
      query,
    };
  } catch {
    return null;
  }
};

const normalizeSelectedValue = (value: string) =>
  decodeSelectedSuggestion(value)
    ? value
    : '';

const readStickyOffsetPx = (): number => {
  const rootStyle = window.getComputedStyle(
    document.documentElement,
  );
  const raw = rootStyle
    .getPropertyValue('--app-sticky-offset')
    .trim();

  if (!raw) return 0;

  if (raw.endsWith('px')) {
    const value = Number.parseFloat(raw);
    return Number.isFinite(value) ? value : 0;
  }

  if (raw.endsWith('rem') || raw.endsWith('em')) {
    const value = Number.parseFloat(raw);
    const rootFontSize = Number.parseFloat(
      rootStyle.fontSize || '16',
    );
    if (!Number.isFinite(value) || !Number.isFinite(rootFontSize)) {
      return 0;
    }
    return value * rootFontSize;
  }

  const fallback = Number.parseFloat(raw);
  return Number.isFinite(fallback) ? fallback : 0;
};

const previewStorageKey = (mode: SearchMode) => `cyclopedia_recent_${mode}`;

const loadRecentPreviewCards = (mode: SearchMode): CyclopediaPreviewCard[] => {
  try {
    const raw = localStorage.getItem(previewStorageKey(mode));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CyclopediaPreviewCard[];
    return parsed.slice(0, 10);
  } catch {
    return [];
  }
};

const saveRecentPreviewCards = (mode: SearchMode, cards: CyclopediaPreviewCard[]): void => {
  try {
    const existing = loadRecentPreviewCards(mode);
    const byId = new Map<string, CyclopediaPreviewCard>();
    for (const card of [...cards, ...existing]) {
      if (!byId.has(card.id)) byId.set(card.id, card);
    }
    localStorage.setItem(previewStorageKey(mode), JSON.stringify(Array.from(byId.values()).slice(0, 10)));
  } catch {
    // Ignore storage errors.
  }
};

const mergeUniqueCreatures = (current: CreatureSimple[], incoming: CreatureSimple[]): CreatureSimple[] => {
  if (incoming.length === 0) return current;
  const seen = new Set(current.map((item) => item.id));
  const merged = [...current];
  for (const item of incoming) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    merged.push(item);
  }
  return merged;
};

const rawZoneExperience = (zone: HuntZone): number => {
  const seen = new Set<number>();
  return (zone.creature_spawns || []).reduce((total, spawn) => {
    const creature = spawn.creature;
    if (!creature || seen.has(creature.id)) return total;
    seen.add(creature.id);
    return total + Math.max(0, creature.experience || 0);
  }, 0);
};

const isLocalCategoryMediaUrl = (
  value?: string,
): value is string =>
  Boolean(
    value &&
      (
        value.startsWith('/') ||
        value.startsWith('data:') ||
        value.startsWith('blob:')
      ),
  );

function CreatureCategoryMedia({
  sources,
  label,
  fallback,
}: {
  sources: string[];
  label: string;
  fallback: React.ReactNode;
}) {
  const sourceKey = sources.join('|');
  const [sourceIndex, setSourceIndex] = useState(0);

  useEffect(() => {
    setSourceIndex(0);
  }, [sourceKey]);

  const source = sources[sourceIndex];

  return (
    <span
      title={label}
      className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-lg bg-primary/10 text-primary sm:size-14 sm:rounded-xl"
    >
      {source ? (
        <img
          src={source}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() =>
            setSourceIndex((current) => current + 1)
          }
          className="size-8 object-contain p-0.5 [image-rendering:pixelated] sm:size-13 sm:p-1"
        />
      ) : (
        fallback
      )}
    </span>
  );
}

const CreaturesPage: React.FC = () => {
  const PAGE_SIZE = 20;
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── Initialize mode directly from URL to avoid Effect 2 clobbering the
  //    URL before Effect 1 has a chance to set the correct mode. ──────────
  const [mode, setMode] = useState<SearchMode>(() => {
    const params = new URLSearchParams(window.location.search);
    const tabParam = (params.get('tab') || params.get('section') || '').toLowerCase();
    return (tabToMode(tabParam) as SearchMode) || 'creatures';
  });

  const [searchTerm, setSearchTerm] = useState(() => new URLSearchParams(window.location.search).get('q') || '');
  const [selectedResult, setSelectedResult] = useState(() => normalizeSelectedValue(new URLSearchParams(window.location.search).get('selected') || ''));
  const [creatureSort, setCreatureSort] = useState<CreatureSort>('name');
  const [itemSort, setItemSort] = useState<ItemBrowseSort>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [creatureCategory, setCreatureCategory] = useState<CreatureCategory>('');
  const [itemCategory, setItemCategory] = useState('');
  const [itemCategories, setItemCategories] = useState<ItemCategoryFacet[]>([]);
  const [itemTotal, setItemTotal] = useState(0);
  const [creatures, setCreatures] = useState<CreatureSimple[]>([]);
  const [items, setItems] = useState<ItemSearchResult[]>([]);
  const [quests, setQuests] = useState<QuestSearchResult[]>([]);
  const [zones, setZones] = useState<HuntZone[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [, setUsedHighlightsSource] = useState(false);
  const [showCategories, setShowCategories] = useState(false);
  const [categoryImages, setCategoryImages] = useState<Record<string, string>>({});
  const [categoryPreviews, setCategoryPreviews] = useState<
    Record<string, CreatureCategoryPreview[]>
  >({});
  const [categoryCounts, setCategoryCounts] = useState<
    Record<string, number>
  >({});
  const [, setRecentPreviewCards] = useState<
    CyclopediaPreviewCard[]
  >([]);
  const [mostVisitedPreviewCards, setMostVisitedPreviewCards] = useState<
    CyclopediaPreviewCard[]
  >([]);
  const [topPreviewCards, setTopPreviewCards] = useState<CyclopediaPreviewCard[]>([]);
  const [lootTrendingPreviewCards, setLootTrendingPreviewCards] = useState<CyclopediaPreviewCard[]>([]);
  const [isSearchCompact, setIsSearchCompact] =
    useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] =
    useState(false);
  const [snapshotReadyTick, setSnapshotReadyTick] = useState(0);
  const syncingFromUrlRef = useRef(false);
  const activeRequestRef = useRef<AbortController | null>(null);
  const searchOriginRef = useRef<HTMLDivElement | null>(null);
  const loadMoreSentinelRef = useRef<HTMLDivElement | null>(null);
  const loadMoreLockRef = useRef(false);
  const lastSearchSignatureRef = useRef<string>('');
  const pendingScrollRestoreRef = useRef<number | null>(null);
  const inPageTabSwitchRef = useRef(false);
  const mountedRef = useRef(true);
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      activeRequestRef.current?.abort();
    };
  }, []);

  const selectedSuggestion = useMemo(
    () => decodeSelectedSuggestion(selectedResult),
    [selectedResult],
  );

  const effectiveSearchTerm =
    searchTerm.trim() || selectedSuggestion?.query || '';

  const searchSuggestions = useMemo<
    KnowledgeSuggestion[]
  >(() => {
    if (mode === 'creatures' || mode === 'bosses') {
      return creatures.slice(0, 20).map((creature) => ({
        key: `${mode}:${creature.id}`,
        section: mode,
        kind: mode === 'bosses' ? 'boss' : 'creature',
        label: creature.name,
        to: `/creatures/${creature.slug || creature.id}`,
        imageUrl:
          `/api/v1/creatures/${creature.id}/image` +
          '?placeholder=false',
      }));
    }

    if (mode === 'items') {
      return items.slice(0, 20).map((item) => {
        const imageId = item.image_item_id ?? item.id;
        return {
          key: `item:${item.normalized_name}`,
          section: mode,
          kind: 'item',
          label: item.item_name,
          to: `/items/${item.slug || item.normalized_name.split(' ').join('-')}`,
          imageUrl:
            imageId != null
              ? `/api/v1/items/${imageId}/image` +
                '?placeholder=false'
              : undefined,
        };
      });
    }

    if (mode === 'quests') {
      return quests.slice(0, 20).map((quest) => ({
        key: `quest:${quest.id || quest.slug || quest.name}`,
        section: mode,
        kind: 'quest',
        label: quest.name,
        to:
          quest.slug || quest.id != null
            ? `/quests/${quest.slug || quest.id}`
            : `/cyclopedia?tab=quests&selected=${encodeURIComponent(encodeSelectedSuggestion('quest', quest.name))}`,
      }));
    }

    return zones.slice(0, 20).map((zone) => ({
      key: `zone:${zone.id}`,
      section: mode,
      kind: 'zone',
      label: zone.name,
      to: `/hunt-zones/${zone.slug || zone.id}`,
      imageUrl: `/api/v1/hunt-zones/${zone.id}/map-image`,
    }));
  }, [creatures, items, mode, quests, zones]);

  const resetResults = () => {
    setCreatures([]);
    setItems([]);
    setQuests([]);
    setZones([]);
    setSkip(0);
    setHasMore(false);
    setUsedHighlightsSource(false);
    setErrorMessage(null);
  };

  const errorTitle = mode === 'bosses' ? t('cyclopedia.states.bossErrorTitle') : t('cyclopedia.states.errorTitle');
  const errorSubtitle = mode === 'bosses'
    ? t('cyclopedia.states.bossErrorSubtitle')
    : t('cyclopedia.states.errorSubtitle');
  const emptyTitle = mode === 'bosses' ? t('cyclopedia.states.bossEmptyTitle') : t('cyclopedia.states.creatureEmptyTitle');
  const emptySubtitle = mode === 'bosses'
    ? t('cyclopedia.states.bossEmptySubtitle')
    : t('cyclopedia.states.creatureEmptySubtitle');

  useEffect(() => {
    const stored = localStorage.getItem(
      'cyclopediaShowCategories',
    );

    setShowCategories(stored === '1');
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void Promise.allSettled([
      creaturesApi.getCategoryImages(controller.signal),
      creaturesApi.getCategoryPreviews(controller.signal),
      creaturesApi.getCategoryCounts(controller.signal),
    ]).then(([images, previews, counts]) => {
      if (controller.signal.aborted) return;

      setCategoryImages(
        images.status === 'fulfilled'
          ? images.value || {}
          : {},
      );

      setCategoryPreviews(
        previews.status === 'fulfilled'
          ? previews.value || {}
          : {},
      );

      setCategoryCounts(
        counts.status === 'fulfilled'
          ? counts.value || {}
          : {},
      );
    });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (mode !== 'items') return undefined;

    const controller = new AbortController();
    void itemBrowserApi
      .getFacets(controller.signal)
      .then((facets) => {
        if (controller.signal.aborted) return;
        setItemCategories(facets.categories || []);
        setItemTotal(facets.total || 0);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setItemCategories([]);
        setItemTotal(0);
      });

    return () => controller.abort();
  }, [mode]);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    const loadLandingCards = async () => {
      if (mounted) {
        setMostVisitedPreviewCards([]);
        setLootTrendingPreviewCards([]);
      }

      const localRecent = loadRecentPreviewCards(mode);
      if (mounted) setRecentPreviewCards(localRecent);

      if (isAuthenticated) {
        try {
          const activity = await activityApi.getMine(
            80,
            controller.signal,
          );

          const expectedViewActivity =
            mode === 'creatures'
              ? 'view_creature'
              : mode === 'bosses'
                ? 'view_boss'
                : null;

          if (expectedViewActivity) {
            const visits = new Map<
              string,
              {
                count: number;
                latest: string;
                name: string;
                slug: string;
              }
            >();

            for (const entry of activity) {
              if (
                entry.activity_type !==
                expectedViewActivity
              ) {
                continue;
              }

              const entityId = String(
                entry.entity_id || '',
              ).trim();

              const name = String(
                entry.metadata?.name || '',
              ).trim();

              if (
                !/^\d+$/.test(entityId) ||
                !name
              ) {
                continue;
              }

              const slug = String(
                entry.metadata?.slug || '',
              ).trim();

              const existing =
                visits.get(entityId);

              visits.set(entityId, {
                count:
                  (existing?.count || 0) + 1,
                latest:
                  existing &&
                  existing.latest >
                    entry.created_at
                    ? existing.latest
                    : entry.created_at,
                name,
                slug:
                  slug ||
                  existing?.slug ||
                  '',
              });
            }

            const mostVisited = [
              ...visits.entries(),
            ]
              .sort(
                ([, left], [, right]) =>
                  right.count - left.count ||
                  right.latest.localeCompare(
                    left.latest,
                  ),
              )
              .slice(0, 5)
              .map(([entityId, visit]) => ({
                id:
                  `visited:${mode}:` +
                  entityId,
                name: visit.name,
                subtitle: t(
                  'cyclopedia.cards.visits',
                  {
                    count: visit.count,
                  },
                ),
                to:
                  `/creatures/` +
                  (visit.slug || entityId),
                imageUrl:
                  `/api/v1/creatures/` +
                  `${entityId}/image` +
                  '?placeholder=false',
                createdAt: visit.latest,
              }));

            if (mounted) {
              setMostVisitedPreviewCards(
                mostVisited,
              );
            }
          }

          const cards: CyclopediaPreviewCard[] = [];
          for (const entry of activity) {
            if (entry.activity_type !== 'search') continue;
            if ((entry.entity_type || '').toLowerCase() !== mode) continue;
            const previews = Array.isArray(entry.metadata?.previews) ? entry.metadata?.previews : [];
            for (const preview of previews) {
              if (!preview?.id || !preview?.name || !preview?.to) continue;
              cards.push({
                id: String(preview.id),
                name: String(preview.name),
                subtitle: String(preview.subtitle || (entry.query ? t('cyclopedia.cards.searchWithQuery', { query: entry.query }) : t('cyclopedia.cards.recentSearch'))),
                to: String(preview.to),
                imageUrl: preview.imageUrl ? String(preview.imageUrl) : undefined,
                createdAt: entry.created_at,
              });
            }
          }
          if (mounted && cards.length > 0) {
            const byId = new Map<string, CyclopediaPreviewCard>();
            for (const card of cards) {
              if (!byId.has(card.id)) byId.set(card.id, card);
            }
            setRecentPreviewCards(Array.from(byId.values()).slice(0, 10));
          }
        } catch {
          // Keep local fallback.
        }
      }

      try {
        let top: CyclopediaPreviewCard[] = [];
        if (mode === 'creatures') {
          const data = await creaturesApi.getPopular(
            12,
            controller.signal,
          );

          top = data.map((creature) => ({
            id: `creature:${creature.id}`,
            name: creature.name,
            subtitle: t(
              'cyclopedia.cards.experience',
              {
                value:
                  creature.experience?.toLocaleString() ?? t('common.unknown'),
              },
            ),
            to: `/creatures/${
              creature.slug || creature.id
            }`,
            imageUrl:
              `/api/v1/creatures/${creature.id}/image` +
              '?placeholder=false',
          }));
        } else if (mode === 'bosses') {
          const data = await creaturesApi.getPopularBosses(12, controller.signal);
          top = data.map((c) => ({ id: `boss:${c.id}`, name: c.name, subtitle: c.difficulty || t('cyclopedia.cards.boss'), to: `/creatures/${c.slug || c.id}`, imageUrl: `/api/v1/creatures/${c.id}/image` }));
        } else if (mode === 'items') {
          const [data, trendingData] = await Promise.all([
            itemsApi.getPopular(12, controller.signal),
            itemsApi.getTrending(12, controller.signal),
          ]);

          top = data.map((item) => ({
            id: `item:${item.normalized_name}`,
            name: item.item_name,
            subtitle: t(
              'cyclopedia.cards.drops',
              {
                count: item.drops?.length || 0,
              },
            ),
            to: `/items/${item.slug || item.normalized_name.split(' ').join('-')}`,
            imageUrl:
              `/api/v1/items/` +
              `${item.image_item_id ?? item.id}/image`,
          }));
          setLootTrendingPreviewCards(trendingData.map((item) => ({
            id: `trending-item:${item.normalized_name}`,
            name: item.item_name,
            subtitle: t('cyclopedia.cards.drops', { count: item.drops?.length || 0 }),
            to: `/items/${item.slug || item.normalized_name.split(' ').join('-')}`,
            imageUrl: `/api/v1/items/${item.image_item_id ?? item.id}/image`,
          })));
        } else if (mode === 'quests') {
          const data = await questsApi.getHighlights(5, controller.signal);
          top = data.map((q) => ({ id: `quest:${q.id || q.name}`, name: q.name, subtitle: q.group_name || t('cyclopedia.cards.quest'), to: q.slug || q.id ? `/quests/${q.slug || q.id}` : '/cyclopedia?tab=quests' }));
        } else {
          const data = await huntZonesApi.getHighlights(5, controller.signal);
          top = data.map((z) => ({ id: `zone:${z.id}`, name: z.name, subtitle: z.region || z.city || t('cyclopedia.cards.huntZone'), to: `/hunt-zones/${z.slug || z.id}`, imageUrl: `/api/v1/hunt-zones/${z.id}/map-image` }));
        }
        if (mounted) setTopPreviewCards(top);
      } catch {
        if (mounted) setTopPreviewCards([]);
      }
    };

    void loadLandingCards();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [mode, isAuthenticated, t]);

  // On mount: check if we have a scroll-restore snapshot from a prior navigation
  useEffect(() => {
    // Fire-and-forget version check — invalidates cache if server data changed
    void checkAndInvalidateIfStale();
  }, []);

  useEffect(() => {
    if (inPageTabSwitchRef.current) {
      inPageTabSwitchRef.current = false;
      pendingScrollRestoreRef.current = null;
      setSnapshotReadyTick((value) => value + 1);
      return;
    }

    const snapshot = loadSnapshot(mode);
    if (snapshot?.scrollY && snapshot.scrollY > 0) {
      pendingScrollRestoreRef.current = snapshot.scrollY;
    }
    setSnapshotReadyTick((value) => value + 1);
  }, [mode]);

  const toggleCategories = () => {
    setShowCategories((current) => {
      const next = !current;
      localStorage.setItem('cyclopediaShowCategories', next ? '1' : '0');
      return next;
    });
  };

  async function performSearch(reset: boolean = true) {
    if (reset) {
      activeRequestRef.current?.abort();
      activeRequestRef.current = null;
      loadMoreLockRef.current = false;
      setLoadingMore(false);
    }
    const normalized = effectiveSearchTerm.trim();
    const nextSkip = reset ? 0 : skip;
    const cacheCategory = mode === 'creatures'
      ? creatureCategory
      : mode === 'items'
        ? itemCategory
        : '';
    const cacheSort = mode === 'items' ? itemSort : creatureSort;
    const requiresRemoteFetch = mode === 'creatures'
      ? true
      : mode === 'bosses'
        ? true
        : mode === 'items'
          ? true
          : mode === 'quests'
            ? normalized.length > 1
            : normalized.length > 0;

    if (reset && !requiresRemoteFetch) {
      const key = buildCacheKey({
        mode,
        search: normalized,
        category: cacheCategory,
        sort: cacheSort,
        order: sortOrder,
        skip: 0,
      });
      const cached = cacheGet<{
        creatures: CreatureSimple[];
        items: ItemSearchResult[];
        quests: QuestSearchResult[];
        zones: HuntZone[];
        hasMore: boolean;
        usedHighlightsSource: boolean;
      }>(key);

      if (cached) {
        setCreatures(cached.creatures);
        setItems(cached.items);
        setQuests(cached.quests);
        setZones(cached.zones);
        setHasMore(cached.hasMore);
        setUsedHighlightsSource(cached.usedHighlightsSource);
        setSkip(cached.creatures.length + cached.items.length + cached.quests.length + cached.zones.length);
      } else {
        setCreatures([]);
        setItems([]);
        setQuests([]);
        setZones([]);
        setHasMore(false);
        setSkip(0);
        setUsedHighlightsSource(false);
        cacheSet(key, { creatures: [], items: [], quests: [], zones: [], hasMore: false, usedHighlightsSource: false });
      }

      setErrorMessage(null);
      setInitialLoaded(true);
      setLoading(false);
      if (pendingScrollRestoreRef.current !== null) {
        const y = pendingScrollRestoreRef.current;
        pendingScrollRestoreRef.current = null;
        requestAnimationFrame(() => window.scrollTo({ top: y, behavior: 'instant' }));
      }
      return;
    }

    // ── In-memory cache check (only on fresh resets, not "load more") ──
    if (reset) {
      const key = buildCacheKey({
        mode,
        search: normalized,
        category: cacheCategory,
        sort: cacheSort,
        order: sortOrder,
        skip: 0,
      });
      const cached = cacheGet<{
        creatures: CreatureSimple[];
        items: ItemSearchResult[];
        quests: QuestSearchResult[];
        zones: HuntZone[];
        hasMore: boolean;
        usedHighlightsSource: boolean;
      }>(key);
      if (cached) {
        setCreatures(cached.creatures);
        setItems(cached.items);
        setQuests(cached.quests);
        setZones(cached.zones);
        setHasMore(cached.hasMore);
        setUsedHighlightsSource(cached.usedHighlightsSource);
        setSkip(cached.creatures.length + cached.items.length + cached.quests.length + cached.zones.length);
        setInitialLoaded(true);
        setLoading(false);
        // Restore scroll if returning from a detail page
        if (pendingScrollRestoreRef.current !== null) {
          const y = pendingScrollRestoreRef.current;
          pendingScrollRestoreRef.current = null;
          requestAnimationFrame(() => window.scrollTo({ top: y, behavior: 'instant' }));
        }
        return;
      }
    }

    if (
      !reset &&
      loadMoreLockRef.current
    ) {
      return;
    }

    if (!reset) {
      loadMoreLockRef.current = true;
    }

    activeRequestRef.current?.abort();
    const controller = new AbortController();
    activeRequestRef.current = controller;

    if (reset) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }

    setErrorMessage(null);

    // Local accumulator for cache writing at the end of each branch
    let _cacheResult: Parameters<typeof cacheSet>[1] | null = null;
    let searchPreviewCards: CyclopediaPreviewCard[] = [];

    try {
      if (mode === 'creatures') {
        const data = await creaturesApi.getAll(
          {
            skip: nextSkip,
            limit: PAGE_SIZE,
            search: normalized || undefined,
            is_boss: false,
            sort_by: creatureSort,
            sort_order: sortOrder,
            category:
              creatureCategory || undefined,
          },
          controller.signal,
        );
        if (controller.signal.aborted || activeRequestRef.current !== controller) return;

        setCreatures((current) =>
          reset
            ? data
            : mergeUniqueCreatures(
                current,
                data,
              ),
        );

        setSkip(nextSkip + data.length);
        setHasMore(
          data.length === PAGE_SIZE,
        );
        setUsedHighlightsSource(false);

        setItems([]);
        setQuests([]);
        setZones([]);

        searchPreviewCards = data
          .slice(0, 5)
          .map((creature) => ({
            id: `creature:${creature.id}`,
            name: creature.name,
            subtitle:
              creature.difficulty ||
              t('cyclopedia.cards.creature'),
            to: `/creatures/${
              creature.slug || creature.id
            }`,
            imageUrl:
              `/api/v1/creatures/${creature.id}/image` +
              '?placeholder=false',
          }));

        if (reset) {
          _cacheResult = {
            creatures: data,
            items: [],
            quests: [],
            zones: [],
            hasMore:
              data.length === PAGE_SIZE,
            usedHighlightsSource: false,
          };
        }
      } else if (mode === 'bosses') {
        const data = await creaturesApi.getBosses(
          {
            skip: nextSkip,
            limit: PAGE_SIZE,
            search: normalized || undefined,
            sort_by: creatureSort,
            sort_order: sortOrder,
          },
          controller.signal,
        );
        if (controller.signal.aborted || activeRequestRef.current !== controller) return;
        setCreatures((current) => (reset ? data : mergeUniqueCreatures(current, data)));
        setSkip(nextSkip + data.length);
        setHasMore(data.length === PAGE_SIZE);
        setUsedHighlightsSource(false);
        setItems([]);
        setQuests([]);
        setZones([]);
        searchPreviewCards = data.slice(0, 5).map((c) => ({
          id: `boss:${c.id}`,
          name: c.name,
          subtitle: c.difficulty || t('cyclopedia.cards.boss'),
          to: `/creatures/${c.slug || c.id}`,
          imageUrl: `/api/v1/creatures/${c.id}/image`,
        }));
        if (reset) _cacheResult = { creatures: data, items: [], quests: [], zones: [], hasMore: data.length === PAGE_SIZE, usedHighlightsSource: false };
      } else if (mode === 'items') {
        let data: ItemSearchResult[] = [];
        if (normalized.length !== 1) {
          data = await itemBrowserApi.browse(
            {
              search: normalized.length > 1 ? normalized : undefined,
              category: itemCategory || undefined,
              sort_by: itemSort,
              sort_order: sortOrder,
              skip: nextSkip,
              limit: PAGE_SIZE,
            },
            controller.signal,
          );
        }
        if (controller.signal.aborted || activeRequestRef.current !== controller) return;
        setItems((current) => reset ? data : [...current, ...data.filter((row) => !current.some((existing) => existing.normalized_name === row.normalized_name))]);
        setSkip(nextSkip + data.length);
        setHasMore(data.length === PAGE_SIZE);
        setCreatures([]);
        setQuests([]);
        setZones([]);
        searchPreviewCards = data.slice(0, 5).map((i) => ({
          id: `item:${i.normalized_name}`,
          name: i.item_name,
          subtitle: t('cyclopedia.cards.drops', { count: i.drops.length }),
          to: `/items/${i.slug || i.normalized_name.split(' ').join('-')}`,
          imageUrl: i.image_item_id ? `/api/v1/items/${i.image_item_id}/image` : undefined,
        }));
        if (reset) _cacheResult = { creatures: [], items: data, quests: [], zones: [], hasMore: data.length === PAGE_SIZE, usedHighlightsSource: false };
      } else if (mode === 'quests') {
        let data: QuestSearchResult[] = [];
        if (normalized.length > 1) {
          data = await questsApi.search(normalized, PAGE_SIZE, controller.signal, false, nextSkip);
        } else {
          data = [];
        }
        if (controller.signal.aborted || activeRequestRef.current !== controller) return;
        setQuests((current) => reset ? data : [...current, ...data.filter((row) => !current.some((existing) => (existing.id || existing.slug || existing.name) === (row.id || row.slug || row.name)))]);
        setSkip(nextSkip + data.length);
        setHasMore(data.length === PAGE_SIZE);
        setCreatures([]);
        setItems([]);
        setZones([]);
        searchPreviewCards = data.slice(0, 5).map((q) => ({
          id: `quest:${q.id || q.name}`,
          name: q.name,
          subtitle: q.group_name || t('cyclopedia.cards.quest'),
          to: q.slug || q.id ? `/quests/${q.slug || q.id}` : '/cyclopedia?tab=quests',
        }));
        if (reset) _cacheResult = { creatures: [], items: [], quests: data, zones: [], hasMore: data.length === PAGE_SIZE, usedHighlightsSource: false };
      } else {
        const data = normalized
          ? await huntZonesApi.getAll({ search: normalized || undefined, skip: nextSkip, limit: PAGE_SIZE }, controller.signal)
          : [];
        if (controller.signal.aborted || activeRequestRef.current !== controller) return;
        setZones((current) => reset ? data : [...current, ...data.filter((row) => !current.some((existing) => existing.id === row.id))]);
        setSkip(nextSkip + data.length);
        setHasMore(data.length === PAGE_SIZE);
        setCreatures([]);
        setItems([]);
        setQuests([]);
        searchPreviewCards = data.slice(0, 5).map((z) => ({
          id: `zone:${z.id}`,
          name: z.name,
          subtitle: z.region || z.city || t('cyclopedia.cards.huntZone'),
          to: `/hunt-zones/${z.slug || z.id}`,
          imageUrl: `/api/v1/hunt-zones/${z.id}/map-image`,
        }));
        if (reset) _cacheResult = { creatures: [], items: [], quests: [], zones: data, hasMore: data.length === PAGE_SIZE, usedHighlightsSource: false };
      }

      // Write to in-memory cache for fast tab switching
      if (reset && _cacheResult !== null) {
        cacheSet(
          buildCacheKey({ mode, search: normalized, category: cacheCategory, sort: cacheSort, order: sortOrder, skip: 0 }),
          _cacheResult,
        );
      }

      if (isAuthenticated && normalized.length > 1) {
        if (searchPreviewCards.length > 0) {
          saveRecentPreviewCards(mode, searchPreviewCards);
          setRecentPreviewCards(loadRecentPreviewCards(mode));
        }
        const signature = `${mode}:${normalized.toLowerCase()}`;
        if (lastSearchSignatureRef.current !== signature) {
          lastSearchSignatureRef.current = signature;
          void activityApi.record({
            activity_type: 'search',
            entity_type: mode,
            query: normalized,
            metadata: {
              previews: searchPreviewCards,
            },
          }).catch(() => {
            // Keep search flow unaffected if activity endpoint fails.
          });
        }
      } else if (normalized.length > 1 && searchPreviewCards.length > 0) {
        saveRecentPreviewCards(mode, searchPreviewCards);
        setRecentPreviewCards(loadRecentPreviewCards(mode));
      }
    } catch (error: any) {
      if (axios.isCancel(error) || error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
        return;
      }
      if (activeRequestRef.current !== controller || !mountedRef.current) return;
      console.error(error);

      if (reset) {
        resetResults();
      }

      setErrorMessage(
        error?.response?.data?.detail ||
          error?.message ||
          'Failed to load cyclopedia data',
      );
    } finally {
      const isCurrent = activeRequestRef.current === controller;
      if (!reset) loadMoreLockRef.current = false;
      if (!isCurrent || !mountedRef.current) return;
      activeRequestRef.current = null;
      if (reset) setLoading(false);
      else setLoadingMore(false);

      setInitialLoaded(true);
      // Restore scroll position if returning from a detail page (cache miss path)
      if (pendingScrollRestoreRef.current !== null) {
        const y = pendingScrollRestoreRef.current;
        pendingScrollRestoreRef.current = null;
        requestAnimationFrame(() => window.scrollTo({ top: y, behavior: 'instant' }));
      }
    }
  }

  // Keep state synchronized when users navigate with direct URLs/back-forward.
  useEffect(() => {
    syncingFromUrlRef.current = true;

    const tabParam = (searchParams.get('tab') || searchParams.get('section') || '').toLowerCase();
    const nextMode = (tabToMode(tabParam) as SearchMode) || 'creatures';
    const nextQuery = searchParams.get('q') || '';
    const nextSelected = normalizeSelectedValue(searchParams.get('selected') || '');
    const nextCreatureCategory =
      nextMode === 'creatures'
        ? normalizeCreatureCategory(
            searchParams.get('category'),
          )
        : '';
    const nextItemCategory = nextMode === 'items'
      ? searchParams.get('category') || ''
      : '';
    const nextSortParam = searchParams.get('sort');
    const nextOrderParam = searchParams.get('order') as SortOrder | null;
    const nextCreatureSort = nextMode === 'creatures' || nextMode === 'bosses'
      ? nextSortParam && ['name', 'experience', 'hitpoints', 'difficulty'].includes(nextSortParam)
        ? nextSortParam as CreatureSort
        : 'name'
      : 'name';
    const nextItemSort = nextMode === 'items' && nextSortParam === 'category'
      ? 'category'
      : 'name';
    const nextOrder = nextOrderParam === 'desc' ? 'desc' : 'asc';

    setMode(nextMode);
    setSearchTerm(nextQuery);
    setSelectedResult(nextSelected);
    setCreatureCategory(nextCreatureCategory);
    setItemCategory(nextItemCategory);
    setCreatureSort(nextCreatureSort);
    setItemSort(nextItemSort);
    setSortOrder(nextOrder);

    const token = window.setTimeout(() => {
      syncingFromUrlRef.current = false;
      setSnapshotReadyTick((value) => value + 1);
    }, 0);

    return () => window.clearTimeout(token);
  }, [searchParams]);

  // Keep URL synchronized with current page state (replace to avoid keypress history spam).
  useEffect(() => {
    if (syncingFromUrlRef.current) return;

    const nextPath = buildCyclopediaPath({
      tab: modeToTab(mode),
      q: searchTerm,
      selected: selectedResult,
      category: mode === 'creatures' ? creatureCategory : mode === 'items' ? itemCategory : '',
      sort: (mode === 'creatures' || mode === 'bosses')
        ? creatureSort !== 'name' ? creatureSort : undefined
        : mode === 'items' && itemSort !== 'name'
          ? itemSort
          : undefined,
      order: (mode === 'creatures' || mode === 'bosses' || mode === 'items') && sortOrder !== 'asc' ? sortOrder : undefined,
    });

    const nextQuery = nextPath.split('?')[1] || '';
    const nextParams = new URLSearchParams(nextQuery);
    const currentParams = new URLSearchParams(searchParams);
    currentParams.delete('section');

    if (nextParams.toString() !== currentParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [
    mode,
    searchTerm,
    selectedResult,
    creatureCategory,
    itemCategory,
    creatureSort,
    itemSort,
    sortOrder,
    searchParams,
    setSearchParams,
  ]);

  // Effect 3: debounced search. Cache check is done inside performSearch.
  useEffect(() => {
    if (syncingFromUrlRef.current) return;
    const timer = setTimeout(() => {
      void performSearch(true);
    }, 450);
    return () => {
      clearTimeout(timer);
      activeRequestRef.current?.abort();
    };
  }, [searchTerm, selectedResult, mode, creatureSort, itemSort, sortOrder, creatureCategory, itemCategory, snapshotReadyTick]);

  // Persist scroll position + state when navigating away (e.g. to creature detail).
  useEffect(() => {
    const activeCategory = mode === 'creatures' ? creatureCategory : mode === 'items' ? itemCategory : '';
    const activeSort = mode === 'items' ? itemSort : creatureSort;
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveSnapshot({
          mode,
          searchTerm,
          selected: selectedResult,
          category: activeCategory,
          sort: activeSort,
          order: sortOrder,
          scrollY: window.scrollY,
          savedAt: Date.now(),
        });
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      // Also save on unmount (route change)
      saveSnapshot({
        mode,
        searchTerm,
        selected: selectedResult,
        category: activeCategory,
        sort: activeSort,
        order: sortOrder,
        scrollY: window.scrollY,
        savedAt: Date.now(),
      });
    };
  }, [mode, searchTerm, selectedResult, creatureCategory, itemCategory, creatureSort, itemSort, sortOrder]);

  const hasActiveQuery = searchTerm.trim().length > 0 || selectedResult.trim().length > 0 || (mode === 'creatures' && !!creatureCategory) || (mode === 'items' && !!itemCategory);

  const creatureResultCount =
    mode === 'creatures' &&
    !effectiveSearchTerm.trim()
      ? categoryCounts[
          normalizeCategoryKey(
            creatureCategory || 'all',
          )
        ] ?? creatures.length
      : creatures.length;

  const itemResultCount =
    mode === 'items' && !effectiveSearchTerm.trim()
      ? itemCategory
        ? itemCategories.find((facet) => facet.value === itemCategory)?.count ?? items.length
        : itemTotal || items.length
      : items.length;

  const isEmpty = hasActiveQuery && !loading && creatures.length === 0 && items.length === 0 && quests.length === 0 && zones.length === 0;

  const cyclopediaPath = useMemo(
    () =>
      buildCyclopediaPath({
        tab: modeToTab(mode),
        q: searchTerm,
        selected: selectedResult,
        category: mode === 'creatures' ? creatureCategory : mode === 'items' ? itemCategory : '',
        sort: (mode === 'creatures' || mode === 'bosses')
          ? creatureSort !== 'name' ? creatureSort : undefined
          : mode === 'items' && itemSort !== 'name'
            ? itemSort
            : undefined,
        order: (mode === 'creatures' || mode === 'bosses' || mode === 'items') && sortOrder !== 'asc' ? sortOrder : undefined,
      }),
    [mode, searchTerm, selectedResult, creatureCategory, itemCategory, creatureSort, itemSort, sortOrder],
  );

  const cyclopediaRouteState = useMemo(
    () => createCyclopediaRouteState(cyclopediaPath),
    [cyclopediaPath],
  );

  const persistCyclopediaState = () => {
    saveSnapshot({
      mode,
      searchTerm,
      selected: selectedResult,
      category: mode === 'creatures' ? creatureCategory : mode === 'items' ? itemCategory : '',
      sort: mode === 'items' ? itemSort : creatureSort,
      order: sortOrder,
      scrollY: window.scrollY,
      savedAt: Date.now(),
    });
    saveCyclopediaReturnTarget(cyclopediaPath);
  };

  const handleQueryChange = (value: string) => {
    setSearchTerm(value);
    if (value.trim() && selectedResult) {
      setSelectedResult('');
    }
  };

  const handleSuggestionSelect = (
    suggestion: KnowledgeSuggestion,
  ) => {
    const isQuestDetail =
      suggestion.kind === 'quest' &&
      suggestion.to.startsWith('/quests/');

    if (
      suggestion.kind === 'creature' ||
      suggestion.kind === 'boss' ||
      isQuestDetail
    ) {
      persistCyclopediaState();
      navigate(suggestion.to, {
        state: cyclopediaRouteState,
      });
      return;
    }

    if (suggestion.kind === 'item') {
      setSelectedResult(
        encodeSelectedSuggestion('item', suggestion.label),
      );
    } else if (suggestion.kind === 'zone') {
      setSelectedResult(
        encodeSelectedSuggestion('zone', suggestion.label),
      );
    } else {
      setSelectedResult(
        encodeSelectedSuggestion('quest', suggestion.label),
      );
    }

    setSearchTerm('');
  };

  useEffect(() => {
    saveCyclopediaReturnTarget(cyclopediaPath);
  }, [cyclopediaPath]);

  useEffect(() => {
    let frame = 0;

    const updateCompactState = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        const origin = searchOriginRef.current;
        if (!origin) return;
        const shouldCompact =
          origin.getBoundingClientRect().top <= readStickyOffsetPx();
        setIsSearchCompact((current) =>
          current === shouldCompact ? current : shouldCompact,
        );
      });
    };

    updateCompactState();
    window.addEventListener('scroll', updateCompactState, { passive: true });
    window.addEventListener('resize', updateCompactState);

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', updateCompactState);
      window.removeEventListener('resize', updateCompactState);
    };
  }, []);

  useEffect(() => {
    if (!isSearchCompact) {
      setMobileSearchOpen(false);
    }
  }, [isSearchCompact, mode]);

  useEffect(() => {
    const sentinel =
      loadMoreSentinelRef.current;
    const canAutoPaginate =
      mode === 'creatures' ||
      mode === 'bosses' ||
      mode === 'items' ||
      effectiveSearchTerm.trim().length > 0;

    if (
      !sentinel ||
      !hasMore ||
      loading ||
      loadingMore ||
      errorMessage ||
      !canAutoPaginate
    ) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0]?.isIntersecting &&
          !loadMoreLockRef.current
        ) {
          void performSearch(false);
        }
      },
      {
        root: null,
        rootMargin:
          '0px 0px 650px 0px',
        threshold: 0,
      },
    );

    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [
    hasMore,
    loading,
    loadingMore,
    errorMessage,
    mode,
    creatures.length,
    items.length,
    quests.length,
    zones.length,
    skip,
    searchTerm,
    selectedResult,
    creatureCategory,
    itemCategory,
    creatureSort,
    itemSort,
    sortOrder,
  ]);

  // P7 — lightweight prefetch for other tabs after initial load.
  // Runs once, 3 s after first successful data load, only caches highlights.
  useEffect(() => {
    if (!initialLoaded) return;
    const MODES: SearchMode[] = ['creatures', 'bosses', 'items', 'quests', 'zones'];
    const others = MODES.filter((m) => m !== mode);
    const timer = window.setTimeout(async () => {
      for (const m of others) {
        const key = buildCacheKey({ mode: m, search: '', category: '', sort: 'name', order: 'asc', skip: 0 });
        if (cacheGet(key)) continue; // already warm
        try {
          if (m === 'creatures') {
            const data = await creaturesApi.getAll({
              skip: 0,
              limit: 12,
              is_boss: false,
              sort_by: 'name',
              sort_order: 'asc',
            });

            cacheSet(key, {
              creatures: data,
              items: [],
              quests: [],
              zones: [],
              hasMore: data.length === 12,
              usedHighlightsSource: false,
            });
          } else if (m === 'bosses') {
            const data = await creaturesApi.getBosses({ skip: 0, limit: 12 });
            cacheSet(key, { creatures: data, items: [], quests: [], zones: [], hasMore: true, usedHighlightsSource: false });
          } else if (m === 'items') {
            const data = await itemBrowserApi.browse({ skip: 0, limit: PAGE_SIZE, sort_by: 'name', sort_order: 'asc' });
            cacheSet(key, { creatures: [], items: data, quests: [], zones: [], hasMore: data.length === PAGE_SIZE, usedHighlightsSource: false });
          } else if (m === 'quests') {
            const data = await questsApi.list({ skip: 0, limit: 20 });
            cacheSet(key, { creatures: [], items: [], quests: data, zones: [], hasMore: false, usedHighlightsSource: false });
          } else if (m === 'zones') {
            const data = await huntZonesApi.getHighlights(12);
            cacheSet(key, { creatures: [], items: [], quests: [], zones: data, hasMore: false, usedHighlightsSource: false });
          }
        } catch {
          // Prefetch failure is silent — doesn't affect main UX
        }
      }
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [initialLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetTabFilters = () => {
    setCreatureCategory('');
    setItemCategory('');
    setCreatureSort('name');
    setItemSort('name');
    setSortOrder('asc');
  };

  return (
    <Page className="space-y-6">
      <div className="contents">
        <div className="ds-enter mb-5">
          <PageHeader
            title={t('nav.search')}
            subtitle={t('hero.subtitle')}
            icon={faBook}
            size="md"
          />
        </div>

        <div ref={searchOriginRef} className="h-px w-full" aria-hidden="true" />
        <div
          className={`mx-auto mb-5 w-full ${
            isSearchCompact
              ? 'app-sticky-offset sticky z-sticky'
              : 'relative z-base'
          }`}
        >
          <AppCard
            className={`flex flex-col shadow-2xl ${
              isSearchCompact
                ? 'gap-1 border-primary/20 bg-surface-overlay/95 p-1 backdrop-blur-xl'
                : 'gap-2 p-2'
            }`}
          >
            {!isSearchCompact &&
            (mode === 'creatures' || mode === 'bosses') &&
            mostVisitedPreviewCards.length > 0 ? (
              <div>
                <CompactEntityStrip
                  title={t(
                    'cyclopedia.cards.mostVisited',
                  )}
                  items={
                    mostVisitedPreviewCards
                  }
                  variant="chips"
                  linkState={cyclopediaRouteState}
                  onNavigate={persistCyclopediaState}
                />
              </div>
            ) : null}
            <div
              className={
                isSearchCompact
                  ? 'flex min-w-0 items-center gap-1'
                  : ''
              }
            >
              <AppTabs
                className={
                  isSearchCompact
                    ? 'min-w-0 flex-1 overflow-x-auto'
                    : 'min-w-0'
                }
                compact={isSearchCompact}
                iconOnly={isSearchCompact}
                activeKey={mode}
                onChange={(key) => {
                  const nextMode = key as SearchMode;
                  inPageTabSwitchRef.current = true;
                  setMode(nextMode);
                  setSearchTerm('');
                  setSelectedResult('');
                  resetTabFilters();
                  pendingScrollRestoreRef.current = null;
                  setMobileSearchOpen(false);
                }}
                items={cyclopediaSections.map(
                  (section) => ({
                    key: section.mode,
                    label: t(section.i18nLabel),
                    icon: (
                      <KnowledgeCategoryIcon
                        category={section.mode}
                        label={t(
                          section.i18nLabel,
                        )}
                        className="size-7"
                        mediaClassName="size-6"
                      />
                    ),
                  }),
                )}
              />

              {isSearchCompact ? (
                <button
                  type="button"
                  title={t('nav.search')}
                  aria-label={t('nav.search')}
                  aria-expanded={
                    mobileSearchOpen
                  }
                  onClick={() =>
                    setMobileSearchOpen(
                      (current) => !current,
                    )
                  }
                  className="app-button-ghost grid size-9 shrink-0 place-items-center rounded-lg md:hidden"
                >
                  {mobileSearchOpen ? (
                    <X className="size-4" />
                  ) : (
                    <Search className="size-4" />
                  )}
                </button>
              ) : null}
            </div>

            {!isSearchCompact ? (
              <KnowledgeSearchBox
                section={mode}
                query={searchTerm}
                onSectionChange={(nextMode) => {
                  inPageTabSwitchRef.current = true;
                  setMode(nextMode);
                  setSearchTerm('');
                  setSelectedResult('');
                  resetTabFilters();
                  pendingScrollRestoreRef.current = null;
                }}
                onQueryChange={handleQueryChange}
                onSuggestionSelect={handleSuggestionSelect}
                showSectionSelect={false}
                externalSuggestions={
                  searchSuggestions
                }
                externalLoading={loading}
              />
            ) : (
              <>
                <div className="hidden md:block">
                  <KnowledgeSearchBox
                    section={mode}
                    query={searchTerm}
                    onSectionChange={(
                      nextMode,
                    ) => {
                      inPageTabSwitchRef.current = true;
                      setMode(nextMode);
                      setSearchTerm('');
                      setSelectedResult('');
                      resetTabFilters();
                      pendingScrollRestoreRef.current = null;
                    }}
                    onQueryChange={handleQueryChange}
                    onSuggestionSelect={handleSuggestionSelect}
                    showSectionSelect={false}
                    externalSuggestions={
                      searchSuggestions
                    }
                    externalLoading={loading}
                    compact
                  />
                </div>

                {mobileSearchOpen ? (
                  <div className="md:hidden">
                    <KnowledgeSearchBox
                      section={mode}
                      query={searchTerm}
                      onSectionChange={(
                        nextMode,
                      ) => {
                        inPageTabSwitchRef.current = true;
                        setMode(nextMode);
                        setSearchTerm('');
                        setSelectedResult('');
                        resetTabFilters();
                        pendingScrollRestoreRef.current = null;
                      }}
                      onQueryChange={handleQueryChange}
                      onSuggestionSelect={handleSuggestionSelect}
                      showSectionSelect={false}
                      externalSuggestions={
                        searchSuggestions
                      }
                      externalLoading={loading}
                      compact
                    />
                  </div>
                ) : null}
              </>
            )}

            {(mode === 'creatures' || mode === 'bosses') && !isSearchCompact ? (
              <div className="space-y-2">
                {mode === 'creatures' && (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={toggleCategories}
                      className="app-button-ghost h-9 px-3 text-xs"
                    >
                      {showCategories ? t('cyclopedia.categories.hide') : t('cyclopedia.categories.show')}
                    </button>
                  </div>
                )}

                {mode === 'creatures' && showCategories && (
                  <div className="grid grid-cols-5 gap-1.5 sm:grid-cols-3 sm:gap-3 lg:grid-cols-6">
                    {CREATURE_CATEGORIES.map((category) => {
                      const active =
                        creatureCategory === category;
                      const CategoryIcon =
                        iconByCategory(category);
                      const categoryKey =
                        normalizeCategoryKey(
                          category || 'all',
                        );

                      const categoryCount =
                        categoryCounts[categoryKey] ?? 0;

                      const configuredImage =
                        categoryImages[categoryKey];

                      const previewSources = (
                        categoryPreviews[categoryKey] || []
                      ).map(
                        (preview) =>
                          `/api/v1/creatures/${preview.id}/image?placeholder=false`,
                      );

                      const mediaSources = Array.from(
                        new Set(
                          [
                            isLocalCategoryMediaUrl(
                              configuredImage,
                            )
                              ? configuredImage
                              : undefined,
                            ...previewSources,
                          ].filter(
                            (value): value is string =>
                              Boolean(value),
                          ),
                        ),
                      );

                      const label =
                        category ||
                        t('cyclopedia.categories.all');

                      return (
                        <button
                          key={category || 'all'}
                          type="button"
                          aria-label={label}
                          title={label}
                          onClick={() =>
                            setCreatureCategory(category)
                          }
                          className={`app-stone-panel group relative h-16 min-h-0 rounded-lg p-1 text-center transition sm:h-auto sm:min-h-[6.5rem] sm:rounded-xl sm:px-3 sm:py-3 sm:text-left ${
                            active
                              ? 'ring-1 ring-primary text-content-primary'
                              : 'text-content-muted hover:text-content-primary'
                          }`}
                        >
                          <span className="absolute right-1 top-1 rounded-full bg-surface-overlay/90 px-1.5 py-0.5 text-[9px] font-semibold leading-none text-content-secondary sm:hidden">
                            {categoryCount.toLocaleString()}
                          </span>

                          <div className="flex h-full items-center justify-center sm:h-auto sm:justify-start sm:gap-3">
                            <CreatureCategoryMedia
                              sources={mediaSources}
                              label={label}
                              fallback={
                                <CategoryIcon className="text-primary" />
                              }
                            />

                            <span className="hidden min-w-0 sm:block">
                              <span className="block truncate text-sm font-semibold">
                                {label}
                              </span>
                              <span className="mt-1 block text-[10px] uppercase tracking-wide opacity-75">
                                {category
                                  ? t(
                                      'cyclopedia.categories.browse',
                                    )
                                  : t(
                                      'cyclopedia.categories.overview',
                                    )}
                                {' · '}
                                {categoryCount.toLocaleString()}
                              </span>
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : null}

            {(mode === 'creatures' && creatureCategory) || (mode === 'items' && itemCategory) || selectedSuggestion ? (
              <div className="flex flex-wrap items-center gap-2 px-1 pb-1">
                {mode === 'creatures' && creatureCategory ? (
                  <span className="inline-flex min-h-9 items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 text-xs font-semibold text-primary">
                    {t('cyclopedia.filters.categoryLabel', {
                      category: creatureCategory,
                    })}
                    <button
                      type="button"
                      title={t('cyclopedia.filters.clearCategory')}
                      aria-label={t('cyclopedia.filters.clearCategory')}
                      onClick={() => setCreatureCategory('')}
                      className="rounded p-0.5 text-primary transition hover:bg-primary/20"
                    >
                      <X className="size-3.5" />
                    </button>
                  </span>
                ) : null}

                {mode === 'items' && itemCategory ? (
                  <span className="inline-flex min-h-9 items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 text-xs font-semibold text-primary">
                    {t('cyclopedia.filters.categoryLabel', {
                      category: itemCategory,
                    })}
                    <button
                      type="button"
                      title={t('cyclopedia.filters.clearCategory')}
                      aria-label={t('cyclopedia.filters.clearCategory')}
                      onClick={() => setItemCategory('')}
                      className="rounded p-0.5 text-primary transition hover:bg-primary/20"
                    >
                      <X className="size-3.5" />
                    </button>
                  </span>
                ) : null}

                {selectedSuggestion ? (
                  <span className="inline-flex min-h-9 items-center gap-2 rounded-full border border-info/30 bg-info/10 px-3 text-xs font-semibold text-info">
                    {t('cyclopedia.filters.selectedResult', {
                      value: selectedSuggestion.query,
                    })}
                    <button
                      type="button"
                      title={t('cyclopedia.filters.clearSelectedResult')}
                      aria-label={t('cyclopedia.filters.clearSelectedResult')}
                      onClick={() => setSelectedResult('')}
                      className="rounded p-0.5 text-info transition hover:bg-info/20"
                    >
                      <X className="size-3.5" />
                    </button>
                  </span>
                ) : null}
              </div>
            ) : null}
          </AppCard>
        </div>

        {!searchTerm.trim() &&
        !selectedResult.trim() &&
        !creatureCategory &&
        !itemCategory ? (
          mode === 'creatures' ? (
            <CompactEntityStrip
              title={t(
                'cyclopedia.discovery.mostPopularCreatures',
              )}
              items={topPreviewCards}
              variant="rail"
              nudgeSessionKey="popular-creatures"
              linkState={cyclopediaRouteState}
              onNavigate={persistCyclopediaState}
            />
          ) : mode === 'bosses' ? (
            <CompactEntityStrip
              title={t('cyclopedia.discovery.popularBosses')}
              items={topPreviewCards}
              variant="rail"
              nudgeSessionKey="popular-bosses"
              linkState={cyclopediaRouteState}
              onNavigate={persistCyclopediaState}
            />
          ) : mode === 'items' ? (
            <div className="space-y-4 rounded-2xl border border-line bg-surface-raised/60 p-4">
              <CompactEntityStrip title={t('cyclopedia.discovery.popularLoot')} items={topPreviewCards} variant="rail" nudgeSessionKey="popular-loot" linkState={cyclopediaRouteState} onNavigate={persistCyclopediaState} />
              <CompactEntityStrip title={t('cyclopedia.discovery.trendingLoot')} items={lootTrendingPreviewCards} variant="rail" nudgeSessionKey="trending-loot" linkState={cyclopediaRouteState} onNavigate={persistCyclopediaState} />
            </div>
          ) : mode === 'quests' ? null : (
            <CyclopediaDiscovery
              mode={mode}
              primaryItems={topPreviewCards}
              linkState={cyclopediaRouteState}
              onNavigate={persistCyclopediaState}
            />
          )
        ) : null}
      </div>

      {mode === 'quests' ? (
        <QuestLibraryShelves
          linkState={cyclopediaRouteState}
          onNavigate={persistCyclopediaState}
        />
      ) : null}

      <div>
        {!loading &&
        (mode === 'creatures' || mode === 'bosses') ? (
          <div className="mb-4 grid gap-3 rounded-xl border border-line bg-surface-base/50 p-3 md:grid-cols-[minmax(0,1fr)_14rem_auto] md:items-center">
            <div className="min-w-0 text-sm text-content-secondary">
              {mode === 'creatures' && creatureCategory ? (
                <span className="inline-flex items-center rounded bg-surface px-2 py-1 text-xs font-semibold text-content-secondary">
                  {t('cyclopedia.filters.categoryLabel', { category: creatureCategory })}
                </span>
              ) : null}
              <p className="mt-1 text-xs text-content-muted">
                {t('cyclopedia.filters.resultCount', { count: creatureResultCount })}
              </p>
            </div>

            <select value={creatureSort} onChange={(event) => setCreatureSort(event.target.value as CreatureSort)} className="app-input">
              <option value="name">{t('cyclopedia.sort.name')}</option>
              <option value="experience">{t('cyclopedia.sort.experience')}</option>
              <option value="hitpoints">{t('cyclopedia.sort.hitpoints')}</option>
              <option value="difficulty">{t('cyclopedia.sort.difficulty')}</option>
            </select>

            <button onClick={() => setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')} className="app-button-ghost inline-flex items-center justify-center gap-2">
              {sortOrder === 'asc' ? <ArrowDownAZ size={16} /> : <ArrowUpAZ size={16} />}
              {sortOrder === 'asc' ? t('cyclopedia.sort.ascending') : t('cyclopedia.sort.descending')}
            </button>
          </div>
        ) : null}

        {!loading && mode === 'items' ? (
          <div className="mb-4 grid gap-3 rounded-xl border border-line bg-surface-base/50 p-3 md:grid-cols-[minmax(0,1fr)_minmax(12rem,18rem)_14rem_auto] md:items-center">
            <div className="min-w-0 text-sm text-content-secondary">
              {itemCategory ? (
                <span className="inline-flex items-center rounded bg-surface px-2 py-1 text-xs font-semibold text-content-secondary">
                  {t('cyclopedia.filters.categoryLabel', { category: itemCategory })}
                </span>
              ) : null}
              <p className="mt-1 text-xs text-content-muted">
                {t('cyclopedia.filters.resultCount', { count: itemResultCount })}
              </p>
            </div>

            <select value={itemCategory} onChange={(event) => setItemCategory(event.target.value)} className="app-input">
              <option value="">{t('cyclopedia.categories.all')}</option>
              {itemCategories.map((facet) => (
                <option key={facet.value} value={facet.value}>
                  {facet.value} ({facet.count.toLocaleString()})
                </option>
              ))}
            </select>

            <select value={itemSort} onChange={(event) => setItemSort(event.target.value as ItemBrowseSort)} className="app-input">
              <option value="name">{t('cyclopedia.sort.name')}</option>
              <option value="category">{t('themePlayground.forms.category')}</option>
            </select>

            <button onClick={() => setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')} className="app-button-ghost inline-flex items-center justify-center gap-2">
              {sortOrder === 'asc' ? <ArrowDownAZ size={16} /> : <ArrowUpAZ size={16} />}
              {sortOrder === 'asc' ? t('cyclopedia.sort.ascending') : t('cyclopedia.sort.descending')}
            </button>
          </div>
        ) : null}

        {loading && (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-primary" size={48} />
          </div>
        )}

        {!loading && errorMessage && (
          <div className="mx-auto mb-8 max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-5 text-danger">
            <div className="mb-2 flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-4 w-4" /> {errorTitle}
            </div>
            <p className="text-sm text-danger/80">{errorSubtitle}</p>
            <button
              onClick={() => void performSearch(true)}
              className="mt-3 rounded-lg border border-danger/30 bg-danger/20 px-3 py-1.5 text-sm text-danger hover:bg-danger/30"
            >
              {t('common.retry')}
            </button>
          </div>
        )}

        {!loading && (
          <>
            <div
              className={
                mode === 'quests'
                  ? 'grid grid-cols-1 gap-4 lg:grid-cols-2'
                  : 'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
              }
            >
            {(mode === 'creatures' || mode === 'bosses') && creatures.map((creature, index) => (
              <div key={creature.id} data-cyclopedia-result className="contents"><CreatureCard creature={creature} index={index} linkState={cyclopediaRouteState} onNavigate={persistCyclopediaState} /></div>
            ))}

            {mode === 'items' && items.map((item, index) => (
              <AppCard key={`${item.normalized_name}-${index}`} data-cyclopedia-result className="ds-enter overflow-hidden p-0">
                <div className="flex items-start gap-4 p-4 sm:p-5">
                  <ImageWithFallback
                    src={item.image_item_id ? `/api/v1/items/${item.image_item_id}/image?placeholder=false` : item.item_image_url || null}
                    alt={item.item_name}
                    className="size-14 object-contain [image-rendering:pixelated]"
                    containerClassName="grid size-16 shrink-0 place-items-center rounded-xl border border-line bg-surface-base/60"
                    fallbackLabel={item.item_name}
                  />
                  <div className="min-w-0 flex-1">
                    <Link to={`/items/${item.slug || item.normalized_name.split(' ').join('-')}`} state={cyclopediaRouteState} onClick={persistCyclopediaState} className="text-lg font-bold text-content-primary hover:text-primary hover:underline">{item.item_name}</Link>
                    <div className="mt-2 flex flex-wrap gap-2">{item.item_type ? <KnowledgeBadge>{item.item_type}</KnowledgeBadge> : null}{item.category ? <KnowledgeBadge>{item.category}</KnowledgeBadge> : null}{item.drops.length ? <KnowledgeBadge tone="primary">{t('cyclopedia.items.creaturesMatched', { count: item.drops.length })}</KnowledgeBadge> : null}</div>
                  </div>
                </div>
                {item.drops.length > 0 ? (
                  <div className="space-y-2 border-t border-line bg-surface-base/30 px-4 py-3 text-sm text-content-secondary sm:px-5">
                    {item.drops.slice(0, 3).map((drop) => (
                      <div key={`${item.normalized_name}-${drop.creature_id ?? drop.creature_name}`} className="flex flex-wrap items-center gap-2">
                        {drop.creature_slug || drop.creature_id ? <Link to={`/creatures/${drop.creature_slug || drop.creature_id}`} state={cyclopediaRouteState} onClick={persistCyclopediaState} className="font-medium text-primary hover:underline">{drop.creature_name}</Link> : <span className="font-medium text-content-primary">{drop.creature_name}</span>}
                        {drop.is_boss ? <KnowledgeBadge tone="danger">{t('itemDetail.boss')}</KnowledgeBadge> : null}
                        {drop.chance != null ? <KnowledgeBadge>{t('itemDetail.chance', { value: drop.chance })}</KnowledgeBadge> : null}
                        {drop.rarity ? <KnowledgeBadge>{drop.rarity}</KnowledgeBadge> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </AppCard>
            ))}

            {mode === 'zones' && zones.map((zone) => <div key={zone.id} data-cyclopedia-result className="ds-enter h-full"><HuntZoneCard zone={zone} linkState={cyclopediaRouteState} onNavigate={persistCyclopediaState} rawExperience={rawZoneExperience(zone)} /></div>)}
            </div>
          </>
        )}

        {hasMore && (creatures.length + items.length + quests.length + zones.length) > 0 ? (
          <div
            ref={loadMoreSentinelRef}
            className="h-px w-full"
            aria-hidden="true"
          />
        ) : null}

        {loadingMore ? (
          <div
            className="flex items-center justify-center gap-2 py-5 text-sm text-content-muted"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="size-4 animate-spin text-primary" />
            {t('common.loading')}
          </div>
        ) : null}

        {isEmpty && mode !== 'quests' && !errorMessage && (
          <div className="py-20 text-center opacity-70">
            <div className="mb-4 text-5xl text-primary"><FontAwesomeIcon icon={faScroll} /></div>
            <p className="font-serif text-xl text-content-secondary">{emptyTitle}</p>
            <p className="mt-2 text-sm text-content-muted">{emptySubtitle}</p>
          </div>
        )}
      </div>
    </Page>
  );
};

export default CreaturesPage;
