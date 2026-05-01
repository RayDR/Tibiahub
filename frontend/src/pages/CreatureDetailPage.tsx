import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowLeft, Gem, Heart, Info, Loader2, MapPin, Shield, Skull, Swords, Zap } from 'lucide-react';

import { creaturesApi } from '../services/api';
import type { Creature } from '../types';

const formatNumber = (value?: number | null): string => {
  if (value === null || value === undefined) return 'Unknown';
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return `${value}`;
};

const CreatureDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [creature, setCreature] = useState<Creature | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchCreature = async () => {
      if (!id) return;
      try {
        setLoading(true);
        setErrorMessage(null);
        const data = await creaturesApi.getById(Number.parseInt(id, 10));
        setCreature(data);
      } catch (error: any) {
        console.error('Failed to load creature details', error);
        setErrorMessage(error?.response?.data?.detail || error?.message || 'Failed to load creature details');
      } finally {
        setLoading(false);
      }
    };
    void fetchCreature();
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-amber-500">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="animate-spin" size={48} />
          <p className="text-lg font-serif">Summoning creature details...</p>
        </div>
      </div>
    );
  }

  if (!creature || errorMessage) {
    return (
      <div className="mx-auto max-w-3xl rounded-2xl border border-red-500/20 bg-red-950/20 p-6 text-red-100">
        <div className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <AlertTriangle className="h-5 w-5" /> Creature detail unavailable
        </div>
        <p className="text-sm text-red-200/80">{errorMessage || 'Creature not found'}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-20 pt-28">
      <div className="relative mb-8">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-amber-500/10 to-transparent" />
        <div className="container relative z-10 mx-auto px-4">
          <button onClick={() => navigate('/')} className="group mb-6 flex items-center gap-2 text-slate-400 transition-colors hover:text-white">
            <ArrowLeft size={18} className="transition-transform group-hover:-translate-x-1" />
            Back to Bestiary
          </button>

          <div className="flex flex-col items-start gap-8 md:flex-row">
            <motion.div initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="relative aspect-square w-full overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/80 p-8 shadow-2xl shadow-black/50 md:w-64">
              <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-red-500/5" />
              {creature.image_url ? (
                <img src={`/api/v1/creatures/${creature.id}/image`} alt={creature.name} className="h-full w-full object-contain drop-shadow-[0_0_15px_rgba(0,0,0,0.6)]" />
              ) : (
                <div className="flex h-full items-center justify-center"><Skull size={80} className="text-slate-700 opacity-50" /></div>
              )}
            </motion.div>

            <div className="flex-1 space-y-6">
              <div>
                <motion.h1 initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="mb-2 text-4xl font-serif font-bold tracking-tight text-white md:text-6xl">
                  {creature.name}
                </motion.h1>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-1 font-semibold text-amber-300">{creature.difficulty || 'Unknown difficulty'}</span>
                  <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-slate-300">{creature.occurrence || 'Unknown occurrence'}</span>
                  <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-slate-300">Bestiary: {creature.bestiary_class || 'Unknown'}</span>
                  <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-slate-300">Charm points: {creature.charm_points ?? 'Unknown'}</span>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: 'Hitpoints', value: formatNumber(creature.hitpoints), icon: Heart, color: 'text-rose-400' },
                  { label: 'Experience', value: formatNumber(creature.experience), icon: Gem, color: 'text-amber-400' },
                  { label: 'Armor', value: formatNumber(creature.armor), icon: Shield, color: 'text-slate-100' },
                  { label: 'Speed', value: formatNumber(creature.speed), icon: Zap, color: 'text-yellow-200' },
                  { label: 'Max damage', value: formatNumber(creature.max_damage), icon: Swords, color: 'text-red-400' },
                  { label: 'Primary type', value: creature.primary_type || 'Unknown', icon: Info, color: 'text-cyan-300' },
                  { label: 'Creature class', value: creature.creature_class || 'Unknown', icon: Skull, color: 'text-purple-300' },
                  { label: 'Bestiary level', value: creature.bestiary_level || 'Unknown', icon: Gem, color: 'text-emerald-300' },
                ].map((stat) => (
                  <div key={stat.label} className="flex items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                    <div className={`rounded-lg bg-slate-950 p-2 ${stat.color}`}>
                      {typeof stat.icon === 'string' ? stat.icon : <stat.icon size={20} />}
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-slate-500">{stat.label}</div>
                      <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto grid gap-8 px-4 lg:grid-cols-12">
        <div className="space-y-8 lg:col-span-8">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-serif font-bold text-amber-500">
              <Info size={20} /> Overview
            </h2>
            <p className="mb-4 text-lg leading-relaxed text-slate-300">{creature.description || 'Not available'}</p>
            <p className="text-sm leading-relaxed text-slate-400">{creature.behavior || 'Behavior not available.'}</p>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h2 className="flex items-center gap-2 text-xl font-serif font-bold text-amber-500">
                <Gem size={20} /> Loot & Drops
              </h2>
              <div className="text-sm text-slate-500">Source values are shown as-is. Unknown means the source did not expose an exact drop chance.</div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {creature.loot_items.length > 0 ? creature.loot_items.map((loot) => (
                <div key={loot.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="mb-2 flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-800 text-lg">💎</div>
                    <div>
                      <div className="font-semibold text-slate-100">{loot.item_name}</div>
                      <div className="text-xs text-slate-500">Rarity: {loot.rarity || 'Unknown'} · Chance: {loot.percentage ?? 'Not available'}</div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-400">Amount: {loot.min_amount} - {loot.max_amount}</div>
                  {loot.source_url && (
                    <a href={loot.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-amber-400 hover:text-amber-300">
                      Source page
                    </a>
                  )}
                </div>
              )) : (
                <div className="text-sm text-slate-500">No drop data available.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-8 lg:col-span-4">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-white">
              <MapPin className="text-amber-500" size={20} /> Known Locations
            </h2>
            <div className="space-y-2 text-sm text-slate-300">
              {creature.locations?.length > 0 ? creature.locations.map((location) => (
                <div key={location} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">{location}</div>
              )) : <div className="text-slate-500">Not available</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 text-lg font-bold text-white">Related Tasks</h2>
            <div className="space-y-2 text-sm text-slate-300">
              {creature.related_tasks?.length > 0 ? creature.related_tasks.map((task) => (
                <div key={task} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">{task}</div>
              )) : <div className="text-slate-500">Not available</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 text-lg font-bold text-white">Sources & Completeness</h2>
            <div className="space-y-2 text-sm text-slate-300">
              <div>Sources: {creature.data_sources?.length > 0 ? creature.data_sources.join(', ') : 'Unknown'}</div>
              <div>Missing fields: {creature.missing_fields?.length > 0 ? creature.missing_fields.join(', ') : 'None'}</div>
              {creature.source_url ? (
                <a href={creature.source_url} target="_blank" rel="noreferrer" className="inline-block text-amber-400 hover:text-amber-300">
                  Open source page
                </a>
              ) : (
                <div className="text-slate-500">Source page not available</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreatureDetailPage;
