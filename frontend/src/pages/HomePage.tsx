import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock3, Gem, MapPin, TrendingUp } from 'lucide-react';

import { creaturesApi, huntZonesApi, itemsApi } from '../services/api';
import type { CreatureSimple, HuntZone, ItemSearchResult } from '../types';

interface RecentCreature {
  id: number;
  slug?: string;
  name: string;
  image_url?: string;
  viewed_at: string;
}

const HomePage: React.FC = () => {
  const [featuredCreatures, setFeaturedCreatures] = useState<CreatureSimple[]>([]);
  const [topItems, setTopItems] = useState<ItemSearchResult[]>([]);
  const [topZones, setTopZones] = useState<HuntZone[]>([]);

  useEffect(() => {
    const loadHighlights = async () => {
      try {
        const [creatures, items, zones] = await Promise.all([
          creaturesApi.getHighlights(12),
          itemsApi.getHighlights(8),
          huntZonesApi.getHighlights(6),
        ]);
        setFeaturedCreatures(creatures);
        setTopItems(items);
        setTopZones(zones);
      } catch (error) {
        console.error('Failed to load home highlights', error);
      }
    };

    void loadHighlights();
  }, []);

  const recentCreatures = useMemo<RecentCreature[]>(() => {
    try {
      const raw = localStorage.getItem('recentCreatures');
      if (!raw) return [];
      const parsed = JSON.parse(raw) as RecentCreature[];
      return parsed.slice(0, 8);
    } catch {
      return [];
    }
  }, []);

  return (
    <div className="min-h-screen pb-16 pt-10">
      <section className="mb-10 rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
        <h1 className="text-3xl font-bold text-amber-200 md:text-4xl">TibiaHub Home</h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Explora destacados sin cargar todo el bestiary. Usa la vista completa para buscar criaturas, loot y zonas.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/bestiary" className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400">
            Open Bestiary
          </Link>
        </div>
      </section>

      <section className="mb-10">
        <div className="mb-4 flex items-center gap-2 text-amber-300">
          <TrendingUp size={18} />
          <h2 className="text-xl font-semibold">Destacados</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {featuredCreatures.map((creature) => (
            <Link
              key={creature.id}
              to={`/creatures/${creature.slug || creature.id}`}
              className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 transition hover:border-amber-500/40"
            >
              <div className="mb-2 text-lg font-semibold text-slate-100">{creature.name}</div>
              <div className="text-xs text-slate-400">HP {creature.hitpoints.toLocaleString()} · EXP {creature.experience.toLocaleString()}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <div className="mb-4 flex items-center gap-2 text-amber-300">
          <Gem size={18} />
          <h2 className="text-xl font-semibold">Mas Buscados</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {topItems.map((item) => (
            <div key={item.normalized_name} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
              <div className="text-sm font-semibold text-slate-100">{item.item_name}</div>
              <div className="mt-1 text-xs text-slate-400">{item.drops.length} creatures</div>
            </div>
          ))}
          {topZones.map((zone) => (
            <div key={`zone-${zone.id}`} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <MapPin size={14} /> {zone.name}
              </div>
              <div className="mt-1 text-xs text-slate-400">Min level: {zone.min_level ?? 'N/A'}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center gap-2 text-amber-300">
          <Clock3 size={18} />
          <h2 className="text-xl font-semibold">Recientes</h2>
        </div>
        {recentCreatures.length === 0 ? (
          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm text-slate-400">No recent creatures yet.</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {recentCreatures.map((creature) => (
              <Link key={`recent-${creature.id}`} to={`/creatures/${creature.slug || creature.id}`} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 transition hover:border-amber-500/40">
                <div className="text-sm font-semibold text-slate-100">{creature.name}</div>
                <div className="mt-1 text-xs text-slate-500">Viewed: {new Date(creature.viewed_at).toLocaleString()}</div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default HomePage;
