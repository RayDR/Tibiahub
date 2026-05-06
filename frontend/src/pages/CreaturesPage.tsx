import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowDownAZ, ArrowUpAZ, Crown, Loader2, ScrollText, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBook, faGem, faScroll } from '@fortawesome/free-solid-svg-icons';

import CreatureCard from '../components/CreatureCard';
import TibiaMap from '../components/TibiaMap';
import { creaturesApi, huntZonesApi, itemsApi, questsApi } from '../services/api';
import { CreatureSimple, HuntZone, ItemSearchResult, QuestSearchResult } from '../types';
import PageHeader from '../components/ui/PageHeader';
import AppTabs from '../components/ui/AppTabs';
import AppInput from '../components/ui/AppInput';
import AppCard from '../components/ui/AppCard';
import { cyclopediaSections, modeToTab, tabToMode } from '../config/cyclopediaSections';
import { iconByCategory } from '../components/icons/CategoryIcons';

type SearchMode = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones';
type CreatureSort = 'name' | 'experience' | 'hitpoints' | 'difficulty';
type SortOrder = 'asc' | 'desc';
type CreatureCategory = '' | 'Amphibic' | 'Aquatic' | 'Bird' | 'Construct' | 'Demon' | 'Dragon' | 'Elemental' | 'Fey' | 'Giant' | 'Human' | 'Humanoid' | 'Lycanthrope' | 'Magical' | 'Mammal' | 'Undead' | 'Beast';
const CREATURE_CATEGORIES: CreatureCategory[] = ['', 'Amphibic', 'Aquatic', 'Bird', 'Construct', 'Demon', 'Dragon', 'Elemental', 'Fey', 'Giant', 'Human', 'Humanoid', 'Lycanthrope', 'Magical', 'Mammal', 'Undead', 'Beast'];

interface RecentCreature {
  id: number;
  slug?: string;
  name: string;
  image_url?: string;
  viewed_at: string;
}

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

const CreaturesPage: React.FC = () => {
  const PAGE_SIZE = 20;
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState<SearchMode>('creatures');
  const [searchTerm, setSearchTerm] = useState('');
  const [creatureSort, setCreatureSort] = useState<CreatureSort>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [creatureCategory, setCreatureCategory] = useState<CreatureCategory>('');
  const [creatures, setCreatures] = useState<CreatureSimple[]>([]);
  const [items, setItems] = useState<ItemSearchResult[]>([]);
  const [quests, setQuests] = useState<QuestSearchResult[]>([]);
  const [zones, setZones] = useState<HuntZone[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [mapPreviewFailed, setMapPreviewFailed] = useState<Record<number, boolean>>({});
  const [usedHighlightsSource, setUsedHighlightsSource] = useState(false);
  const [showCategories, setShowCategories] = useState(true);
  const activeRequestRef = useRef<AbortController | null>(null);

  const recentCreatures = useMemo<RecentCreature[]>(() => {
    try {
      const raw = localStorage.getItem('recentCreatures');
      if (!raw) return [];
      const parsed = JSON.parse(raw) as RecentCreature[];
      return parsed.slice(0, 10);
    } catch {
      return [];
    }
  }, [initialLoaded]);

  const searchPlaceholder = (() => {
    if (mode === 'creatures') return t('search.creaturesPlaceholder');
    if (mode === 'bosses') return t('search.bossesPlaceholder');
    if (mode === 'items') return t('search.lootPlaceholder');
    if (mode === 'quests') return t('search.questsPlaceholder');
    return t('search.zonesPlaceholder');
  })();

  useEffect(() => {
    const stored = localStorage.getItem('cyclopediaShowCategories');
    if (stored === '0') {
      setShowCategories(false);
      return;
    }
    if (stored === '1') {
      setShowCategories(true);
      return;
    }
    setShowCategories(window.innerWidth >= 1024);
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
    activeRequestRef.current?.abort();
    const controller = new AbortController();
    activeRequestRef.current = controller;

    setLoading(true);
    setErrorMessage(null);
    try {
      if (mode === 'creatures') {
        const hasFilters = normalized.length > 0 || !!creatureCategory;
        let data: CreatureSimple[] = [];

        if (reset && !hasFilters) {
          // Primary source for home-like bestiary view; backend falls back to local ordered list.
          data = await creaturesApi.getHighlights(PAGE_SIZE, controller.signal);
          if (data.length === 0) {
            data = await creaturesApi.getAll(
              {
                skip: 0,
                limit: PAGE_SIZE,
                sort_by: creatureSort,
                sort_order: sortOrder,
              },
              controller.signal,
            );
            setUsedHighlightsSource(false);
          } else {
            setUsedHighlightsSource(true);
          }
          setCreatures(data);
          setSkip(data.length);
          // Keep pagination available; next pages come from local list endpoint.
          setHasMore(data.length > 0);
          setItems([]);
          setQuests([]);
          setZones([]);
          return;
        }

        const paginationSkip = !reset && usedHighlightsSource && !hasFilters ? creatures.length : nextSkip;
        data = await creaturesApi.getAll(
          {
            skip: paginationSkip,
            limit: PAGE_SIZE,
            search: normalized || undefined,
            sort_by: creatureSort,
            sort_order: sortOrder,
            category: creatureCategory || undefined,
          },
          controller.signal,
        );

        setCreatures((current) => (reset ? data : mergeUniqueCreatures(current, data)));
        setSkip((reset ? 0 : paginationSkip) + data.length);
        setHasMore(data.length === PAGE_SIZE);
        if (hasFilters || !reset) {
          setUsedHighlightsSource(false);
        }
        setItems([]);
        setQuests([]);
        setZones([]);
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
      } else if (mode === 'items') {
        if (normalized.length > 1) {
          const data = await itemsApi.search(normalized, 20, controller.signal);
          setItems(data);
        } else if (normalized.length > 0) {
          setItems([]);
        } else {
          setItems(await itemsApi.getHighlights(12, controller.signal));
        }
        setHasMore(false);
        setCreatures([]);
        setQuests([]);
        setZones([]);
      } else if (mode === 'quests') {
        if (normalized.length > 1) {
          setQuests(await questsApi.search(normalized, 30, controller.signal));
        } else {
          setQuests(await questsApi.list({ skip: 0, limit: 30 }, controller.signal));
        }
        setHasMore(false);
        setCreatures([]);
        setItems([]);
        setZones([]);
      } else {
        const data = normalized
          ? await huntZonesApi.getAll({ search: normalized || undefined, limit: 20 }, controller.signal)
          : await huntZonesApi.getHighlights(12, controller.signal);
        setZones(data);
        setHasMore(false);
        setCreatures([]);
        setItems([]);
        setQuests([]);
      }
    } catch (error: any) {
      if (axios.isCancel(error) || error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
        return;
      }
      console.error(error);
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Failed to load cyclopedia data');
    } finally {
      setLoading(false);
      setInitialLoaded(true);
    }
  }

  useEffect(() => {
    const tabParam = (searchParams.get('tab') || searchParams.get('section') || '').toLowerCase();
    const nextMode = tabToMode(tabParam);
    if (nextMode) {
      setMode(nextMode);
    }
  }, [searchParams]);

  useEffect(() => {
    const urlTab = (searchParams.get('tab') || '').toLowerCase();
    const modeTab = modeToTab(mode);
    if (urlTab !== modeTab) {
      const next = new URLSearchParams(searchParams);
      next.set('tab', modeTab);
      next.delete('section');
      setSearchParams(next, { replace: true });
    }
  }, [mode, searchParams, setSearchParams]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void performSearch(true);
    }, 450);
    return () => {
      clearTimeout(timer);
      activeRequestRef.current?.abort();
    };
  }, [searchTerm, mode, creatureSort, sortOrder, creatureCategory]);

  const isEmpty = !loading && creatures.length === 0 && items.length === 0 && quests.length === 0 && zones.length === 0;

  return (
    <div className="min-h-screen">
      <div className="relative space-y-6 py-12 text-center md:py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <PageHeader
            title={t('hero.title')}
            subtitle={t('hero.subtitle')}
            icon={faBook}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="relative z-20 mx-auto max-w-6xl px-4"
        >
          <AppCard className="flex flex-col gap-2 p-2 shadow-2xl">
            <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center">
              <AppTabs
                className="min-w-0 lg:flex-1"
                activeKey={mode}
                onChange={(key) => setMode(key as SearchMode)}
                items={cyclopediaSections.map((section) => ({
                  key: section.mode,
                  label: t(section.i18nLabel),
                  icon: <FontAwesomeIcon icon={section.icon} className="w-4" />,
                }))}
              />

              <div className="min-w-0 lg:w-[min(420px,40vw)]">
                <AppInput
                  search
                  type="text"
                  placeholder={searchPlaceholder}
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void performSearch(true);
                    }
                  }}
                  onSearch={() => {
                    void performSearch(true);
                  }}
                  searchAriaLabel={t('a11y.search')}
                  className="h-12"
                />
              </div>
            </div>

            {(mode === 'creatures' || mode === 'bosses') && (
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
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-8">
                    {CREATURE_CATEGORIES.map((category) => {
                      const active = creatureCategory === category;
                      const CategoryIcon = iconByCategory(category);
                      return (
                        <button
                          key={category || 'all'}
                          onClick={() => setCreatureCategory(category)}
                          className={`app-stone-panel rounded-xl px-3 py-2 text-left text-xs transition ${active ? 'ring-1 ring-[color:var(--color-primary)] text-[color:var(--color-text)]' : 'text-[color:var(--color-text-muted)] hover:text-[color:var(--color-text)]'}`}
                        >
                          <div className="mb-1 flex items-center gap-1.5">
                            <CategoryIcon className="text-[color:var(--color-primary)]" />
                            <span className="truncate font-semibold">{category || t('cyclopedia.categories.all')}</span>
                          </div>
                          <div className="text-[10px] uppercase tracking-wide opacity-75">
                            {category ? t('cyclopedia.categories.browse') : t('cyclopedia.categories.overview')}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {mode === 'creatures' && !searchTerm.trim() && !creatureCategory && (
                  <div className="flex items-center gap-2 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-alt)] px-3 py-2 text-xs text-[color:var(--color-text-muted)]">
                    <Sparkles size={14} /> {t('cyclopedia.helpers.classification')}
                  </div>
                )}

                {mode === 'bosses' && (
                  <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                    <Crown size={14} /> {t('cyclopedia.helpers.bosses')}
                  </div>
                )}

                <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-2">
                <select value={creatureSort} onChange={(event) => setCreatureSort(event.target.value as CreatureSort)} className="app-input">
                  <option value="name">Sort by name</option>
                  <option value="experience">Sort by experience</option>
                  <option value="hitpoints">Sort by hitpoints</option>
                  <option value="difficulty">Sort by difficulty</option>
                </select>
                <button onClick={() => setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')} className="app-button-ghost inline-flex items-center justify-center gap-2">
                  {sortOrder === 'asc' ? <ArrowDownAZ size={16} /> : <ArrowUpAZ size={16} />}
                  {sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                </button>
              </div>
              </div>
            )}
          </AppCard>
        </motion.div>
      </div>

      <div className="container mx-auto px-4 pb-20">
        {loading && (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-amber-500" size={48} />
          </div>
        )}

        {!loading && errorMessage && (
          <div className="mx-auto mb-8 max-w-3xl rounded-2xl border border-red-500/20 bg-red-950/20 p-5 text-red-100">
            <div className="mb-2 flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-4 w-4" /> Something went wrong
            </div>
            <p className="text-sm text-red-200/80">Please try again in a moment.</p>
            <button
              onClick={() => void performSearch(true)}
              className="mt-3 rounded-lg border border-red-400/30 bg-red-500/20 px-3 py-1.5 text-sm text-red-100 hover:bg-red-500/30"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && (
          <>
            {mode === 'creatures' && !searchTerm.trim() && !creatureCategory && recentCreatures.length > 0 && (
              <div className="mb-8 rounded-2xl border border-slate-700/50 bg-slate-900/50 p-5">
                <div className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-300">Recent (Last 10)</div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  {recentCreatures.map((entry) => (
                    <Link
                      key={`recent-${entry.id}`}
                      to={`/creatures/${entry.slug || entry.id}`}
                      className="rounded-xl border border-slate-700 bg-slate-950/40 p-3 transition hover:border-amber-500/40"
                    >
                      <div className="truncate text-sm font-semibold text-slate-100">{entry.name}</div>
                      <div className="mt-1 text-xs text-slate-500">{new Date(entry.viewed_at).toLocaleDateString()}</div>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {(mode === 'creatures' || mode === 'bosses') && creatures.map((creature, index) => (
              <CreatureCard key={creature.id} creature={creature} index={index} />
            ))}

            {mode === 'items' && items.map((item, index) => (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} key={`${item.normalized_name}-${index}`} className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6">
                <div className="mb-4 flex items-start gap-3">
                  {item.item_image_url ? (
                    <img src={item.item_image_url} alt={item.item_name} className="h-12 w-12 rounded-lg bg-slate-950/60 object-contain p-1" loading="lazy" />
                  ) : (
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-950/60 text-[color:var(--color-primary)]"><FontAwesomeIcon icon={faGem} /></div>
                  )}
                  <div>
                    <div className="text-xl font-bold text-amber-100">{item.item_name}</div>
                    <div className="text-xs text-slate-500">{item.drops.length} creature{item.drops.length === 1 ? '' : 's'} matched</div>
                  </div>
                </div>
                <div className="space-y-3 text-sm text-slate-300">
                  {item.drops.slice(0, 3).map((drop) => (
                    <div key={`${item.normalized_name}-${drop.creature_id}`} className="rounded-lg bg-slate-950/40 px-3 py-2">
                      <div className="font-medium text-slate-100">{drop.creature_name}</div>
                      <div className="text-xs text-slate-400">Chance: {drop.chance ?? 'Unknown'} · Rarity: {drop.rarity || 'Unknown'}</div>
                      {drop.hunt_zones.length > 0 && (
                        <div className="mt-1 text-xs text-slate-500">Zones: {drop.hunt_zones.slice(0, 2).map((zone) => zone.name).join(', ')}</div>
                      )}
                    </div>
                  ))}
                </div>
                {item.source_url && (
                  <a href={item.source_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-xs text-amber-400 hover:text-amber-300">
                    Source page
                  </a>
                )}
              </motion.div>
            ))}

            {mode === 'quests' && quests.map((quest, index) => (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} key={`${quest.id || quest.name}-${index}`} className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6">
                <div className="mb-3 flex items-start gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-950/60 text-amber-300">
                    <ScrollText size={22} />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-amber-100">{quest.name}</div>
                    <div className="text-xs text-slate-500">Lvl {quest.min_level ?? 'N/A'} - {quest.max_level ?? 'N/A'}</div>
                  </div>
                </div>
                <p className="mb-3 text-sm text-slate-300">{quest.description || 'Description not available.'}</p>
                <div className="text-xs text-slate-500">NPC: {quest.npc || 'Unknown'} · Location: {quest.location || 'Unknown'}</div>
                <div className="mt-4 flex items-center gap-3">
                  {quest.id ? (
                    <Link to={`/quests/${quest.id}`} className="text-xs text-amber-400 hover:text-amber-300">Open quest detail</Link>
                  ) : null}
                  {quest.source_url && (
                    <a href={quest.source_url} target="_blank" rel="noreferrer" className="text-xs text-amber-400 hover:text-amber-300">Source page</a>
                  )}
                </div>
              </motion.div>
            ))}

            {mode === 'zones' && zones.map((zone) => (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} key={zone.id} className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-900/50">
                <div className="relative h-40 bg-slate-950">
                  {zone.map_image_url && !mapPreviewFailed[zone.id] ? (
                    <img
                      src={huntZonesApi.getMapImageUrl(zone.id)}
                      alt={zone.name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={() => setMapPreviewFailed((prev) => ({ ...prev, [zone.id]: true }))}
                    />
                  ) : (
                    <TibiaMap
                      zoom={11}
                      center={zone.location_x ? { x: zone.location_x, y: zone.location_y! } : undefined}
                      markers={zone.location_x ? [{ x: zone.location_x, y: zone.location_y!, label: zone.name }] : []}
                    />
                  )}
                  <div className="absolute inset-0 bg-transparent" />
                </div>
                <div className="p-6">
                  <h3 className="mb-2 text-xl font-bold text-amber-100">{zone.name}</h3>
                  <div className="mb-3 flex gap-2 text-xs text-slate-400">
                    <span className="rounded bg-slate-800 px-2 py-1">{zone.city || 'Unknown'}</span>
                    <span className="rounded bg-slate-800 px-2 py-1">Lvl {zone.min_level ?? 'N/A'}+</span>
                  </div>
                  <div className="text-sm text-slate-400">{zone.difficulty || 'Not available'} difficulty</div>
                </div>
              </motion.div>
            ))}
            </div>
          </>
        )}

        {!loading && (mode === 'creatures' || mode === 'bosses') && hasMore && creatures.length > 0 && (
          <div className="mt-8 flex justify-center">
            <button
              onClick={() => void performSearch(false)}
              className="rounded-xl border border-slate-700 bg-slate-900 px-5 py-3 text-sm font-semibold text-slate-200 hover:border-amber-500/60 hover:text-amber-300"
            >
              Load more
            </button>
          </div>
        )}

        {isEmpty && !errorMessage && (
          <div className="py-20 text-center opacity-70">
            <div className="mb-4 text-5xl text-[color:var(--color-primary)]"><FontAwesomeIcon icon={faScroll} /></div>
            <p className="font-serif text-xl text-slate-300">No creatures found.</p>
            <p className="mt-2 text-sm text-slate-500">Try another search or category.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreaturesPage;
