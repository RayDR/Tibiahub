import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowDownAZ, ArrowUpAZ, Crown, Gem, Loader2, MapPin, ScrollText, Search, Sword, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

import CreatureCard from '../components/CreatureCard';
import TibiaMap from '../components/TibiaMap';
import { creaturesApi, huntZonesApi, itemsApi, questsApi } from '../services/api';
import { CreatureSimple, HuntZone, ItemSearchResult, QuestSearchResult } from '../types';

type SearchMode = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones';
type CreatureSort = 'name' | 'experience' | 'hitpoints' | 'difficulty';
type SortOrder = 'asc' | 'desc';
type CreatureCategory = '' | 'Humanoid' | 'Undead' | 'Demon' | 'Beast' | 'Dragon' | 'Elemental' | 'Construct';
const CREATURE_CATEGORIES: CreatureCategory[] = ['', 'Humanoid', 'Undead', 'Demon', 'Beast', 'Dragon', 'Elemental', 'Construct'];

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
    const section = (searchParams.get('section') || '').toLowerCase();
    if (section === 'creatures' || section === 'bosses' || section === 'quests') {
      setMode(section);
    }
  }, [searchParams]);

  useEffect(() => {
    const currentSection = (searchParams.get('section') || '').toLowerCase();
    if (currentSection !== mode) {
      const next = new URLSearchParams(searchParams);
      next.set('section', mode);
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
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl font-serif font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-200 via-amber-400 to-amber-600 drop-shadow-[0_2px_10px_rgba(245,158,11,0.3)] md:text-6xl"
        >
          {t('hero.title')}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mx-auto max-w-2xl px-4 text-sm text-slate-300 md:text-base"
        >
          Explore the Tibia Cyclopedia your way: by classification first, by direct search, or by your latest viewed creatures.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="relative z-20 mx-auto max-w-4xl px-4"
        >
          <div className="flex flex-col gap-2 rounded-2xl border border-slate-700 bg-slate-900/80 p-2 shadow-2xl backdrop-blur-xl">
            <div className="flex flex-col gap-2 md:flex-row">
              <div className="md:min-w-[220px]">
                <select
                  value={mode}
                  onChange={(event) => setMode(event.target.value as SearchMode)}
                  className="h-full w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none focus:border-amber-500"
                >
                  <option value="creatures">Creatures</option>
                  <option value="bosses">Bosses</option>
                  <option value="quests">Quests</option>
                  <option value="items">Loot</option>
                  <option value="zones">Zones</option>
                </select>
              </div>

              <div className="flex shrink-0 overflow-x-auto rounded-xl bg-slate-950 p-1">
                <button onClick={() => setMode('creatures')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'creatures' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <Sword size={18} />
                  <span className="hidden sm:inline">Creatures</span>
                </button>
                <button onClick={() => setMode('bosses')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'bosses' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <Crown size={18} />
                  <span className="hidden sm:inline">Bosses</span>
                </button>
                <button onClick={() => setMode('items')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'items' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <Gem size={18} />
                  <span className="hidden sm:inline">Loot</span>
                </button>
                <button onClick={() => setMode('quests')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'quests' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <ScrollText size={18} />
                  <span className="hidden sm:inline">Quests</span>
                </button>
                <button onClick={() => setMode('zones')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'zones' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <MapPin size={18} />
                  <span className="hidden sm:inline">Zones</span>
                </button>
              </div>

              <div className="relative flex-1">
                <input
                  type="text"
                  placeholder={mode === 'creatures' ? 'Search creatures (or use classification buttons below)...' : t('search.placeholder')}
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="h-full w-full rounded-xl bg-slate-800/50 pl-12 pr-4 text-white outline-none transition-colors placeholder:text-slate-500 focus:bg-slate-800"
                />
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={20} />
              </div>
            </div>

            {(mode === 'creatures' || mode === 'bosses') && (
              <div className="space-y-2">
                {mode === 'creatures' && (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-8">
                    {CREATURE_CATEGORIES.map((category) => {
                      const active = creatureCategory === category;
                      return (
                        <button
                          key={category || 'all'}
                          onClick={() => setCreatureCategory(category)}
                          className={`rounded-xl border px-3 py-2 text-xs font-semibold transition ${active ? 'border-amber-400 bg-amber-500/20 text-amber-200' : 'border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500'}`}
                        >
                          {category || 'All'}
                        </button>
                      );
                    })}
                  </div>
                )}

                {mode === 'creatures' && !searchTerm.trim() && !creatureCategory && (
                  <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    <Sparkles size={14} /> Classification-first mode active. Pick a category or search directly.
                  </div>
                )}

                {mode === 'bosses' && (
                  <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                    <Crown size={14} /> Search and browse boss encounters.
                  </div>
                )}

                <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-2">
                <select value={creatureSort} onChange={(event) => setCreatureSort(event.target.value as CreatureSort)} className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none focus:border-amber-500">
                  <option value="name">Sort by name</option>
                  <option value="experience">Sort by experience</option>
                  <option value="hitpoints">Sort by hitpoints</option>
                  <option value="difficulty">Sort by difficulty</option>
                </select>
                <button onClick={() => setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 hover:border-slate-500">
                  {sortOrder === 'asc' ? <ArrowDownAZ size={16} /> : <ArrowUpAZ size={16} />}
                  {sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                </button>
              </div>
              </div>
            )}
          </div>
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
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-950/60 text-xl">💎</div>
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
            <div className="mb-4 text-6xl">📜</div>
            <p className="font-serif text-xl text-slate-300">No creatures found.</p>
            <p className="mt-2 text-sm text-slate-500">Try another search or category.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreaturesPage;
