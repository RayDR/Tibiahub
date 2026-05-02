import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowDownAZ, ArrowUpAZ, Gem, Loader2, MapPin, Search, Sword, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

import CreatureCard from '../components/CreatureCard';
import TibiaMap from '../components/TibiaMap';
import { creaturesApi, huntZonesApi, itemsApi } from '../services/api';
import { CreatureSimple, HuntZone, ItemSearchResult } from '../types';

type SearchMode = 'creatures' | 'items' | 'zones';
type CreatureSort = 'name' | 'experience' | 'hitpoints' | 'difficulty';
type SortOrder = 'asc' | 'desc';
type CreatureCategory = '' | 'Humanoid' | 'Undead' | 'Demon' | 'Beast' | 'Dragon' | 'Elemental' | 'Construct';
const CREATURE_CATEGORIES: CreatureCategory[] = ['', 'Humanoid', 'Undead', 'Demon', 'Beast', 'Dragon', 'Elemental', 'Construct'];

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
  const [mode, setMode] = useState<SearchMode>('creatures');
  const [searchTerm, setSearchTerm] = useState('');
  const [creatureSort, setCreatureSort] = useState<CreatureSort>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [creatureCategory, setCreatureCategory] = useState<CreatureCategory>('');
  const [creatures, setCreatures] = useState<CreatureSimple[]>([]);
  const [items, setItems] = useState<ItemSearchResult[]>([]);
  const [zones, setZones] = useState<HuntZone[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [mapPreviewFailed, setMapPreviewFailed] = useState<Record<number, boolean>>({});
  const [usedHighlightsSource, setUsedHighlightsSource] = useState(false);
  const activeRequestRef = useRef<AbortController | null>(null);

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
          data = await creaturesApi.getHighlights(PAGE_SIZE);
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
        setZones([]);
      } else if (mode === 'items') {
        if (normalized.length > 1) {
          const data = await itemsApi.search(normalized, 20, controller.signal);
          setItems(data);
        } else if (normalized.length > 0) {
          setItems([]);
        } else {
          setItems(await itemsApi.getHighlights(12));
        }
        setHasMore(false);
        setCreatures([]);
        setZones([]);
      } else {
        const data = normalized
          ? await huntZonesApi.getAll({ search: normalized || undefined, limit: 20 }, controller.signal)
          : await huntZonesApi.getHighlights(12);
        setZones(data);
        setHasMore(false);
        setCreatures([]);
        setItems([]);
      }
    } catch (error: any) {
      if (axios.isCancel(error) || error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
        return;
      }
      console.error(error);
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Failed to load bestiary data');
    } finally {
      setLoading(false);
      setInitialLoaded(true);
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm || !initialLoaded || mode === 'creatures') {
        void performSearch(true);
      }
    }, 450);
    return () => {
      clearTimeout(timer);
      activeRequestRef.current?.abort();
    };
  }, [searchTerm, mode, creatureSort, sortOrder, creatureCategory]);

  const isEmpty = !loading && creatures.length === 0 && items.length === 0 && zones.length === 0;

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
          Discover creatures, loot, and hunting zones to plan your next adventure.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="relative z-20 mx-auto max-w-4xl px-4"
        >
          <div className="flex flex-col gap-2 rounded-2xl border border-slate-700 bg-slate-900/80 p-2 shadow-2xl backdrop-blur-xl">
            <div className="flex flex-col gap-2 md:flex-row">
              <div className="flex shrink-0 overflow-x-auto rounded-xl bg-slate-950 p-1">
                <button onClick={() => setMode('creatures')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'creatures' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <Sword size={18} />
                  <span className="hidden sm:inline">Monsters</span>
                </button>
                <button onClick={() => setMode('items')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'items' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <Gem size={18} />
                  <span className="hidden sm:inline">Loot</span>
                </button>
                <button onClick={() => setMode('zones')} className={`flex items-center gap-2 rounded-lg px-4 py-3 font-medium transition-all ${mode === 'zones' ? 'bg-amber-500 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>
                  <MapPin size={18} />
                  <span className="hidden sm:inline">Zones</span>
                </button>
              </div>

              <div className="relative flex-1">
                <input
                  type="text"
                  placeholder={t('search.placeholder')}
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="h-full w-full rounded-xl bg-slate-800/50 pl-12 pr-4 text-white outline-none transition-colors placeholder:text-slate-500 focus:bg-slate-800"
                />
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={20} />
              </div>
            </div>

            {mode === 'creatures' && (
              <div className="space-y-2">
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

                {!searchTerm.trim() && !creatureCategory && (
                  <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    <Sparkles size={14} /> Showing recommended creatures.
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
          </div>
        )}

        {!loading && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {mode === 'creatures' && creatures.map((creature, index) => (
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
        )}

        {!loading && mode === 'creatures' && hasMore && creatures.length > 0 && (
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
