import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Link,
  useSearchParams } from 'react-router-dom';
import { AlertTriangle,
  ArrowDownAZ,
  ArrowUpAZ,
  Crown,
  Loader2,
  ScrollText,
  Search,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBook, faScroll } from '@fortawesome/free-solid-svg-icons';

import CreatureCard from '../components/CreatureCard';
import ImageWithFallback from '../components/ImageWithFallback';
import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  questsApi,
  type CreatureCategoryPreview,
} from '../services/api';
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
import { cyclopediaSections, modeToTab, tabToMode } from '../config/cyclopediaSections';
import { iconByCategory } from '../components/icons/CategoryIcons';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import CyclopediaDiscovery from '../components/CyclopediaDiscovery';
import CompactEntityStrip from '../components/CompactEntityStrip';
import CyclopediaTabMedia from '../components/CyclopediaTabMedia';
import KnowledgeSearchBox, {
  type KnowledgeSearchSection,
  type KnowledgeSuggestion,
} from '../components/search/KnowledgeSearchBox';

type SearchMode = KnowledgeSearchSection;
type CreatureSort = 'name' | 'experience' | 'hitpoints' | 'difficulty';
type SortOrder = 'asc' | 'desc';
type CreatureCategory = '' | 'Amphibic' | 'Aquatic' | 'Bird' | 'Construct' | 'Demon' | 'Dragon' | 'Elemental' | 'Fey' | 'Giant' | 'Human' | 'Humanoid' | 'Lycanthrope' | 'Magical' | 'Mammal' | 'Undead' | 'Beast';
const CREATURE_CATEGORIES: CreatureCategory[] = ['', 'Amphibic', 'Aquatic', 'Bird', 'Construct', 'Demon', 'Dragon', 'Elemental', 'Fey', 'Giant', 'Human', 'Humanoid', 'Lycanthrope', 'Magical', 'Mammal', 'Undead', 'Beast'];

interface CyclopediaPreviewCard {
  id: string;
  name: string;
  subtitle: string;
  to: string;
  imageUrl?: string;
  createdAt?: string;
}

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
      className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/10 text-primary"
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
          className="size-13 object-contain p-1 [image-rendering:pixelated]"
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
  const [searchParams, setSearchParams] = useSearchParams();

  // ── Initialize mode directly from URL to avoid Effect 2 clobbering the
  //    URL before Effect 1 has a chance to set the correct mode. ──────────
  const [mode, setMode] = useState<SearchMode>(() => {
    const params = new URLSearchParams(window.location.search);
    const tabParam = (params.get('tab') || params.get('section') || '').toLowerCase();
    return (tabToMode(tabParam) as SearchMode) || 'creatures';
  });

  // Tracks whether mode was just set from a URL navigation (Effect 1) so
  // Effect 2 doesn't immediately push a redundant URL update.
  const urlSyncedRef = useRef(true);
  const [searchTerm, setSearchTerm] = useState(() => new URLSearchParams(window.location.search).get('q') || '');
  const [creatureSort, setCreatureSort] = useState<CreatureSort>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [creatureCategory, setCreatureCategory] = useState<CreatureCategory>('');
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
  const [mapPreviewFailed, setMapPreviewFailed] = useState<Record<number, boolean>>({});
  const [, setUsedHighlightsSource] = useState(false);
  const [showCategories, setShowCategories] = useState(false);
  const [categoryImages, setCategoryImages] = useState<Record<string, string>>({});
  const [categoryPreviews, setCategoryPreviews] = useState<
    Record<string, CreatureCategoryPreview[]>
  >({});
  const [, setRecentPreviewCards] = useState<
    CyclopediaPreviewCard[]
  >([]);
  const [mostVisitedPreviewCards, setMostVisitedPreviewCards] = useState<
    CyclopediaPreviewCard[]
  >([]);
  const [topPreviewCards, setTopPreviewCards] = useState<CyclopediaPreviewCard[]>([]);
  const [tabMedia, setTabMedia] = useState<
    Partial<Record<SearchMode, string>>
  >({});
  const [isSearchCompact, setIsSearchCompact] =
    useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] =
    useState(false);
  const [snapshotReadyTick, setSnapshotReadyTick] = useState(0);
  const activeRequestRef = useRef<AbortController | null>(null);
  const stickySearchRef = useRef<HTMLDivElement | null>(null);
  const loadMoreSentinelRef = useRef<HTMLDivElement | null>(null);
  const loadMoreLockRef = useRef(false);
  const lastSearchSignatureRef = useRef<string>('');
  const pendingScrollRestoreRef = useRef<number | null>(null);
  const applyingSnapshotRef = useRef(false);
  const { isAuthenticated } = useAuth();

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
          to:
            `/cyclopedia?tab=items&q=${encodeURIComponent(
              item.item_name,
            )}`,
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
          quest.id != null
            ? `/quests/${quest.id}`
            : `/cyclopedia?tab=quests&q=${encodeURIComponent(
                quest.name,
              )}`,
      }));
    }

    return zones.slice(0, 20).map((zone) => ({
      key: `zone:${zone.id}`,
      section: mode,
      kind: 'zone',
      label: zone.name,
      to:
        `/cyclopedia?tab=zones&q=${encodeURIComponent(
          zone.name,
        )}`,
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

    void Promise.all([
      creaturesApi.getCategoryImages(controller.signal),
      creaturesApi.getCategoryPreviews(controller.signal),
    ])
      .then(([images, previews]) => {
        setCategoryImages(images || {});
        setCategoryPreviews(previews || {});
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setCategoryImages({});
          setCategoryPreviews({});
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    const loadTabMedia = async () => {
      const [
        popularCreatures,
        bosses,
        lootItems,
        tomeItems,
        zonesForTabs,
      ] = await Promise.all([
        creaturesApi
          .getPopular(1, controller.signal)
          .catch(() => []),
        creaturesApi
          .getBosses(
            {
              skip: 0,
              limit: 1,
            },
            controller.signal,
          )
          .catch(() => []),
        itemsApi
          .getHighlights(12, controller.signal)
          .catch(() => []),
        itemsApi
          .search(
            'Tome of Knowledge',
            5,
            controller.signal,
          )
          .catch(() => []),
        huntZonesApi
          .getHighlights(1, controller.signal)
          .catch(() => []),
      ]);

      if (!mounted) {
        return;
      }

      const lootItem = lootItems.find(
        (item) => item.image_item_id != null,
      );

      const tomeItem =
        tomeItems.find(
          (item) =>
            item.item_name
              .trim()
              .toLowerCase() ===
            'tome of knowledge',
        ) ||
        tomeItems.find(
          (item) =>
            item.image_item_id != null,
        );

      setTabMedia({
        creatures: popularCreatures[0]
          ? `/api/v1/creatures/${popularCreatures[0].id}/image?placeholder=false`
          : undefined,
        bosses: bosses[0]
          ? `/api/v1/creatures/${bosses[0].id}/image?placeholder=false`
          : undefined,
        items:
          lootItem?.image_item_id != null
            ? `/api/v1/items/${lootItem.image_item_id}/image?placeholder=false`
            : undefined,
        quests:
          tomeItem?.image_item_id != null
            ? `/api/v1/items/${tomeItem.image_item_id}/image?placeholder=false`
            : undefined,
        zones: zonesForTabs[0]
          ? `/api/v1/hunt-zones/${zonesForTabs[0].id}/map-image`
          : undefined,
      });
    };

    void loadTabMedia();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    const loadLandingCards = async () => {
      if (mounted) {
        setMostVisitedPreviewCards([]);
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
                  creature.experience.toLocaleString(),
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
          const data = await creaturesApi.getBosses({ skip: 0, limit: 5 }, controller.signal);
          top = data.map((c) => ({ id: `boss:${c.id}`, name: c.name, subtitle: c.difficulty || t('cyclopedia.cards.boss'), to: `/creatures/${c.slug || c.id}`, imageUrl: `/api/v1/creatures/${c.id}/image` }));
        } else if (mode === 'items') {
          const data = (
            await itemsApi.getHighlights(
              20,
              controller.signal,
            )
          )
            .filter(
              (item) =>
                item.image_item_id != null &&
                item.drops.length > 0,
            )
            .slice(0, 5);

          top = data.map((item) => ({
            id: `item:${item.normalized_name}`,
            name: item.item_name,
            subtitle: t(
              'cyclopedia.cards.drops',
              {
                count: item.drops.length,
              },
            ),
            to:
              '/cyclopedia?tab=items&q=' +
              encodeURIComponent(
                item.item_name,
              ),
            imageUrl:
              `/api/v1/items/` +
              `${item.image_item_id}/image` +
              '?placeholder=false',
          }));
        } else if (mode === 'quests') {
          const data = await questsApi.getHighlights(5, controller.signal);
          top = data.map((q) => ({ id: `quest:${q.id || q.name}`, name: q.name, subtitle: q.group_name || t('cyclopedia.cards.quest'), to: q.id ? `/quests/${q.id}` : '/cyclopedia?tab=quests' }));
        } else {
          const data = await huntZonesApi.getHighlights(5, controller.signal);
          top = data.map((z) => ({ id: `zone:${z.id}`, name: z.name, subtitle: z.region || z.city || t('cyclopedia.cards.huntZone'), to: '/cyclopedia?tab=zones', imageUrl: `/api/v1/hunt-zones/${z.id}/map-image` }));
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

  useEffect(() => {
    const snapshot = loadSnapshot(mode);
    applyingSnapshotRef.current = true;

    if (snapshot) {
      setSearchTerm(snapshot.searchTerm || '');
      setCreatureSort((snapshot.sort as CreatureSort) || 'name');
      setSortOrder((snapshot.order as SortOrder) || 'asc');
      setCreatureCategory(mode === 'creatures' ? (snapshot.category as CreatureCategory) || '' : '');
      pendingScrollRestoreRef.current = typeof snapshot.scrollY === 'number' ? snapshot.scrollY : null;
    } else {
      setSearchTerm('');
      setCreatureSort('name');
      setSortOrder('asc');
      setCreatureCategory('');
      pendingScrollRestoreRef.current = null;
    }

    const token = window.setTimeout(() => {
      applyingSnapshotRef.current = false;
      setSnapshotReadyTick((value) => value + 1);
    }, 0);

    return () => window.clearTimeout(token);
  }, [mode]);

  // On mount: check if we have a scroll-restore snapshot from a prior navigation
  useEffect(() => {
    // Fire-and-forget version check — invalidates cache if server data changed
    void checkAndInvalidateIfStale();
    // Restore scroll position for the current tab if we navigated back
    const snapshot = loadSnapshot(mode);
    if (snapshot && snapshot.scrollY > 0) {
      pendingScrollRestoreRef.current = snapshot.scrollY;
    }
  }, []);

  const toggleCategories = () => {
    setShowCategories((current) => {
      const next = !current;
      localStorage.setItem('cyclopediaShowCategories', next ? '1' : '0');
      return next;
    });
  };

  async function performSearch(reset: boolean = true) {
    const normalized = searchTerm.trim();
    const nextSkip = reset ? 0 : skip;
    const requiresRemoteFetch = mode === 'creatures'
      ? true
      : mode === 'bosses'
        ? (!reset || normalized.length > 0)
        : mode === 'items'
          ? normalized.length > 1
          : mode === 'quests'
            ? normalized.length > 1
            : normalized.length > 0;

    if (reset && !requiresRemoteFetch) {
      const key = buildCacheKey({
        mode,
        search: normalized,
        category: creatureCategory,
        sort: creatureSort,
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
        category: creatureCategory,
        sort: creatureSort,
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
        if (normalized.length > 1) {
          data = await itemsApi.search(normalized, 20, controller.signal);
          setItems(data);
        } else if (normalized.length > 0) {
          setItems([]);
        } else {
          setItems([]);
        }
        setHasMore(false);
        setCreatures([]);
        setQuests([]);
        setZones([]);
        searchPreviewCards = data.slice(0, 5).map((i) => ({
          id: `item:${i.normalized_name}`,
          name: i.item_name,
          subtitle: t('cyclopedia.cards.drops', { count: i.drops.length }),
          to: '/cyclopedia?tab=items',
          imageUrl: i.image_item_id ? `/api/v1/items/${i.image_item_id}/image` : undefined,
        }));
        if (reset) _cacheResult = { creatures: [], items: data, quests: [], zones: [], hasMore: false, usedHighlightsSource: false };
      } else if (mode === 'quests') {
        let data: QuestSearchResult[] = [];
        if (normalized.length > 1) {
          data = await questsApi.search(normalized, 30, controller.signal);
        } else {
          data = [];
        }
        setQuests(data);
        setHasMore(false);
        setCreatures([]);
        setItems([]);
        setZones([]);
        searchPreviewCards = data.slice(0, 5).map((q) => ({
          id: `quest:${q.id || q.name}`,
          name: q.name,
          subtitle: q.group_name || t('cyclopedia.cards.quest'),
          to: q.id ? `/quests/${q.id}` : '/cyclopedia?tab=quests',
        }));
        if (reset) _cacheResult = { creatures: [], items: [], quests: data, zones: [], hasMore: false, usedHighlightsSource: false };
      } else {
        const data = normalized
          ? await huntZonesApi.getAll({ search: normalized || undefined, limit: 20 }, controller.signal)
          : [];
        setZones(data);
        setHasMore(false);
        setCreatures([]);
        setItems([]);
        setQuests([]);
        searchPreviewCards = data.slice(0, 5).map((z) => ({
          id: `zone:${z.id}`,
          name: z.name,
          subtitle: z.region || z.city || t('cyclopedia.cards.huntZone'),
          to: '/cyclopedia?tab=zones',
          imageUrl: `/api/v1/hunt-zones/${z.id}/map-image`,
        }));
        if (reset) _cacheResult = { creatures: [], items: [], quests: [], zones: data, hasMore: false, usedHighlightsSource: false };
      }

      // Write to in-memory cache for fast tab switching
      if (reset && _cacheResult !== null) {
        cacheSet(
          buildCacheKey({ mode, search: normalized, category: creatureCategory, sort: creatureSort, order: sortOrder, skip: 0 }),
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
      if (reset) {
        setLoading(false);
      } else {
        setLoadingMore(false);
        loadMoreLockRef.current = false;
      }

      setInitialLoaded(true);
      // Restore scroll position if returning from a detail page (cache miss path)
      if (pendingScrollRestoreRef.current !== null) {
        const y = pendingScrollRestoreRef.current;
        pendingScrollRestoreRef.current = null;
        requestAnimationFrame(() => window.scrollTo({ top: y, behavior: 'instant' }));
      }
    }
  }

  // Effect 1: URL → mode. Fires when the user navigates to a different tab via
  // the navbar dropdown or browser history while the component is already mounted.
  useEffect(() => {
    const tabParam = (searchParams.get('tab') || searchParams.get('section') || '').toLowerCase();
    const nextMode = tabToMode(tabParam);
    if (nextMode && nextMode !== mode) {
      urlSyncedRef.current = true; // tell Effect 2 not to re-push the URL
      setMode(nextMode);
    }
  }, [searchParams]);

  // Keep direct links from Home and browser history synchronized.
  useEffect(() => {
    const nextQuery = searchParams.get('q') || '';

    setSearchTerm((current) =>
      current === nextQuery ? current : nextQuery,
    );
  }, [searchParams]);

  // Effect 2: mode → URL. Only fires when the user clicks an in-page tab
  // (not when Effect 1 already updated the URL). Skipped on first render
  // because mode was initialized from URL in useState.
  useEffect(() => {
    if (urlSyncedRef.current) {
      urlSyncedRef.current = false;
      return;
    }
    const urlTab = (searchParams.get('tab') || '').toLowerCase();
    const modeTab = modeToTab(mode);
    if (urlTab !== modeTab) {
      const next = new URLSearchParams(searchParams);
      next.set('tab', modeTab);
      next.delete('section');
      setSearchParams(next, { replace: true });
    }
  }, [mode, searchParams, setSearchParams]);

  // Effect 3: debounced search. Cache check is done inside performSearch.
  useEffect(() => {
    if (applyingSnapshotRef.current) return;
    const timer = setTimeout(() => {
      void performSearch(true);
    }, 450);
    return () => {
      clearTimeout(timer);
      activeRequestRef.current?.abort();
    };
  }, [searchTerm, mode, creatureSort, sortOrder, creatureCategory, snapshotReadyTick]);

  // Persist scroll position + state when navigating away (e.g. to creature detail).
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveSnapshot({
          mode,
          searchTerm,
          category: creatureCategory,
          sort: creatureSort,
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
        category: creatureCategory,
        sort: creatureSort,
        order: sortOrder,
        scrollY: window.scrollY,
        savedAt: Date.now(),
      });
    };
  }, [mode, searchTerm, creatureCategory, creatureSort, sortOrder]);

  const hasActiveQuery = searchTerm.trim().length > 0 || (mode === 'creatures' && !!creatureCategory);
  const isEmpty = hasActiveQuery && !loading && creatures.length === 0 && items.length === 0 && quests.length === 0 && zones.length === 0;

  useEffect(() => {
    let scheduled = false;

    const updateCompactState = () => {
      if (scheduled) {
        return;
      }

      scheduled = true;

      window.requestAnimationFrame(() => {
        scheduled = false;

        const shouldCompact =
          window.scrollY > 180;

        setIsSearchCompact((current) =>
          current === shouldCompact
            ? current
            : shouldCompact,
        );
      });
    };

    updateCompactState();

    window.addEventListener(
      'scroll',
      updateCompactState,
      { passive: true },
    );

    window.addEventListener(
      'resize',
      updateCompactState,
    );

    return () => {
      window.removeEventListener(
        'scroll',
        updateCompactState,
      );

      window.removeEventListener(
        'resize',
        updateCompactState,
      );
    };
  }, [mode]);

  useEffect(() => {
    if (!isSearchCompact) {
      setMobileSearchOpen(false);
    }
  }, [isSearchCompact, mode]);

  useEffect(() => {
    const sentinel =
      loadMoreSentinelRef.current;

    if (
      !sentinel ||
      !hasMore ||
      loading ||
      loadingMore ||
      errorMessage ||
      (
        mode !== 'creatures' &&
        mode !== 'bosses'
      )
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
    skip,
    searchTerm,
    creatureCategory,
    creatureSort,
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
            const data = await itemsApi.getHighlights(12);
            cacheSet(key, { creatures: [], items: data, quests: [], zones: [], hasMore: false, usedHighlightsSource: false });
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

  return (
    <div className="mx-auto w-full max-w-6xl py-6 sm:py-8">
      <div className="contents">
        <div className="ds-enter mb-5">
          <PageHeader
            title={t('nav.search')}
            subtitle={t('hero.subtitle')}
            icon={faBook}
            size="md"
          />
        </div>

        <div
          ref={stickySearchRef}
          className={`mx-auto mb-5 w-full transition-all duration-200 ${
            isSearchCompact
              ? 'sticky top-[4.5rem] z-40 sm:top-[4.75rem]'
              : 'relative z-20'
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
              (
                mode === 'creatures' ||
                mode === 'bosses'
              ) &&
              mostVisitedPreviewCards.length >
                0 ? (
                <CompactEntityStrip
                  title={t(
                    'cyclopedia.cards.mostVisited',
                  )}
                  items={
                    mostVisitedPreviewCards
                  }
                  variant="chips"
                />
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
                  urlSyncedRef.current = false;
                  setMode(key as SearchMode);
                }}
                items={cyclopediaSections.map(
                  (section) => ({
                    key: section.mode,
                    label: t(section.i18nLabel),
                    icon: (
                      <CyclopediaTabMedia
                        imageUrl={
                          tabMedia[
                            section.mode as SearchMode
                          ]
                        }
                        label={t(
                          section.i18nLabel,
                        )}
                        fallback={
                          <FontAwesomeIcon
                            icon={section.icon}
                            className="w-4"
                          />
                        }
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
                  urlSyncedRef.current = false;
                  setMode(nextMode);
                }}
                onQueryChange={setSearchTerm}
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
                      urlSyncedRef.current =
                        false;
                      setMode(nextMode);
                    }}
                    onQueryChange={
                      setSearchTerm
                    }
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
                        urlSyncedRef.current =
                          false;
                        setMode(nextMode);
                      }}
                      onQueryChange={
                        setSearchTerm
                      }
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

            {!isSearchCompact &&
              (mode === 'creatures' ||
                mode === 'bosses') && (
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
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                    {CREATURE_CATEGORIES.map((category) => {
                      const active =
                        creatureCategory === category;
                      const CategoryIcon =
                        iconByCategory(category);
                      const categoryKey = (
                        category || 'all'
                      ).toLowerCase();

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
                          onClick={() =>
                            setCreatureCategory(category)
                          }
                          className={`app-stone-panel group min-h-[6.5rem] rounded-xl px-3 py-3 text-left transition ${
                            active
                              ? 'ring-1 ring-primary text-content-primary'
                              : 'text-content-muted hover:text-content-primary'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <CreatureCategoryMedia
                              sources={mediaSources}
                              label={label}
                              fallback={
                                <CategoryIcon className="text-primary" />
                              }
                            />

                            <span className="min-w-0">
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
                              </span>
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {mode === 'bosses' && (
                  <div className="flex items-center gap-2 rounded-xl border border-danger/20 bg-danger/10 px-3 py-2 text-xs text-danger">
                    <Crown size={14} /> {t('cyclopedia.helpers.bosses')}
                  </div>
                )}

                <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-2">
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
              </div>
            )}
          </AppCard>
        </div>

        {!searchTerm.trim() &&
        !creatureCategory ? (
          mode === 'creatures' ? (
            <CompactEntityStrip
              title={t(
                'cyclopedia.discovery.mostPopularCreatures',
              )}
              items={topPreviewCards}
              variant="rail"
              nudgeSessionKey="popular-creatures"
            />
          ) : (
            <CyclopediaDiscovery
              mode={mode}
              primaryItems={topPreviewCards}
            />
          )
        ) : null}
      </div>

      <div className="pb-12 pt-6">
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
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {(mode === 'creatures' || mode === 'bosses') && creatures.map((creature, index) => (
              <CreatureCard key={creature.id} creature={creature} index={index} />
            ))}

            {mode === 'items' &&
              searchTerm.trim().length > 1 &&
              items.map((item, index) => (
              <AppCard key={`${item.normalized_name}-${index}`} className="ds-enter p-5">
                <div className="mb-4 flex items-start gap-3">
                  <ImageWithFallback
                    src={item.image_item_id ? `/api/v1/items/${item.image_item_id}/image` : item.item_image_url || null}
                    alt={item.item_name}
                    className="h-12 w-12 rounded-lg bg-surface-base/60 object-contain p-1"
                    containerClassName="h-12 w-12"
                    fallbackLabel={item.item_name}
                  />
                  <div>
                    <div className="text-xl font-bold text-primary">{item.item_name}</div>
                    <div className="text-xs text-content-muted">{t('cyclopedia.items.creaturesMatched', { count: item.drops.length })}</div>
                  </div>
                </div>
                <div className="space-y-3 text-sm text-content-secondary">
                  {item.drops.slice(0, 3).map((drop) => (
                    <div key={`${item.normalized_name}-${drop.creature_id}`} className="rounded-lg bg-surface-base/40 px-3 py-2">
                      <div className="font-medium text-content-primary">{drop.creature_name}</div>
                      <div className="text-xs text-content-secondary">{t('cyclopedia.items.chance')}: {drop.chance ?? t('cyclopedia.states.unknown')} · {t('cyclopedia.items.rarity')}: {drop.rarity || t('cyclopedia.states.unknown')}</div>
                      {drop.hunt_zones.length > 0 && (
                        <div className="mt-1 text-xs text-content-muted">{t('cyclopedia.items.zones')}: {drop.hunt_zones.slice(0, 2).map((zone) => zone.name).join(', ')}</div>
                      )}
                    </div>
                  ))}
                </div>
                {item.source_url && (
                  <a href={item.source_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-xs text-primary hover:text-primary">
                    {t('cyclopedia.items.sourcePage')}
                  </a>
                )}
              </AppCard>
            ))}

            {mode === 'quests' && quests.map((quest, index) => (
              <AppCard key={`${quest.id || quest.name}-${index}`} className="ds-enter p-5">
                <div className="mb-3 flex items-start gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-base/60 text-primary">
                    <ScrollText size={22} />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-primary">{quest.name}</div>
                    {quest.group_name ? (
                      <div className="mt-1 inline-flex rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
                        {t('cyclopedia.quests.group')}: {quest.group_name}
                      </div>
                    ) : null}
                    <div className="text-xs text-content-muted">{t('cyclopedia.quests.levelRange', { min: quest.min_level ?? t('common.notAvailable'), max: quest.max_level ?? t('common.notAvailable') })}</div>
                  </div>
                </div>
                <p className="mb-3 text-sm text-content-secondary">{quest.description || t('cyclopedia.quests.noDetails')}</p>
                <div className="text-xs text-content-muted">{t('cyclopedia.quests.npc')}: {quest.npc || t('cyclopedia.states.unknown')} · {t('cyclopedia.quests.location')}: {quest.location || t('cyclopedia.states.unknown')}</div>
                <div className="mt-4 flex items-center gap-3">
                  {quest.id ? (
                    <Link to={`/quests/${quest.id}`} className="text-xs text-primary hover:text-primary">{t('cyclopedia.quests.openDetail')}</Link>
                  ) : null}
                  {quest.source_url && (
                    <a href={quest.source_url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:text-primary">{t('cyclopedia.items.sourcePage')}</a>
                  )}
                </div>
              </AppCard>
            ))}

            {mode === 'zones' && zones.map((zone) => (
              <AppCard key={zone.id} className="ds-enter overflow-hidden">
                <div className="relative h-40 bg-surface-base">
                  {(zone.map_image_url || zone.map_asset_id) && !mapPreviewFailed[zone.id] ? (
                    <img
                      src={huntZonesApi.getMapImageUrl(zone.id)}
                      alt={zone.name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={() => setMapPreviewFailed((prev) => ({ ...prev, [zone.id]: true }))}
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-surface-base via-surface to-surface-base text-content-secondary">
                      <div className="text-center">
                        <div className="text-sm font-semibold">{t('cyclopedia.zones.mapPreviewUnavailable')}</div>
                        <div className="mt-1 text-xs text-content-secondary">{t('cyclopedia.zones.usingPlaceholder')}</div>
                      </div>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-transparent" />
                </div>
                <div className="p-6">
                  <h3 className="mb-2 text-xl font-bold text-primary">{zone.name}</h3>
                  <div className="mb-3 flex gap-2 text-xs text-content-secondary">
                    <span className="rounded bg-surface px-2 py-1">{zone.region || zone.city || t('cyclopedia.states.unknownRegion')}</span>
                    <span className="rounded bg-surface px-2 py-1">{t('cyclopedia.zones.level', { level: zone.recommended_level ?? zone.min_level ?? t('common.notAvailable') })}</span>
                  </div>
                  <div className="text-sm text-content-secondary">{zone.difficulty || 'Not available'} difficulty</div>
                  <div className="mt-2 text-xs text-content-muted">Source: {zone.source_provider || zone.source_name || 'local'}</div>
                </div>
              </AppCard>
            ))}
            </div>
          </>
        )}

        {(mode === 'creatures' ||
          mode === 'bosses') &&
        hasMore &&
        creatures.length > 0 ? (
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

        {isEmpty && !errorMessage && (
          <div className="py-20 text-center opacity-70">
            <div className="mb-4 text-5xl text-primary"><FontAwesomeIcon icon={faScroll} /></div>
            <p className="font-serif text-xl text-content-secondary">{emptyTitle}</p>
            <p className="mt-2 text-sm text-content-muted">{emptySubtitle}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreaturesPage;
