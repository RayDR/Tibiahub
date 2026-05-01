import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { creaturesApi } from '../services/api';
import type { Creature } from '../types';
import { ArrowLeft, Shield, Swords, Zap, Heart, Star, MapPin, Skull, Gem, Info, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

// Helper for formatting numbers
const formatNumber = (num: number): string => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

const CreatureDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [creature, setCreature] = useState<Creature | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCreature = async () => {
      if (!id) return;
      try {
        setLoading(true);
        const data = await creaturesApi.getById(parseInt(id));
        setCreature(data);
      } catch (err) {
        console.error('Failed to load creature details', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCreature();
  }, [id]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center text-amber-500">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="animate-spin" size={48} />
        <p className="text-lg font-serif">Summoning creature details...</p>
      </div>
    </div>
  );

  if (!creature) return null;

  // Derived stats
  const expPerHour = creature.experience * 100; // Est. 100 kills/hr
  const profitPerHour = (creature.loot_value || 0) * 100;

  return (
    <div className="min-h-screen pb-20 pt-28">

      {/* Hero Header */}
      <div className="relative mb-8">
        <div className="absolute inset-0 bg-gradient-to-b from-amber-500/10 to-transparent pointer-events-none" />
        <div className="container mx-auto px-4 relative z-10">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6 group"
          >
            <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
            Back to Bestiary
          </button>

          <div className="flex flex-col md:flex-row gap-8 items-start">
            {/* Creature Image Box */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full md:w-64 aspect-square bg-slate-900/80 border border-slate-700 rounded-2xl flex items-center justify-center p-8 shadow-2xl shadow-black/50 relative overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-purple-500/5 group-hover:opacity-100 transition-opacity" />
              {creature.image_url ? (
                <img
                  src={`/api/v1/creatures/${creature.id}/image`}
                  alt={creature.name}
                  className="w-full h-full object-contain filter drop-shadow-[0_0_15px_rgba(0,0,0,0.6)]"
                />
              ) : (
                <Skull size={80} className="text-slate-700 opacity-50" />
              )}
              {creature.is_boss && (
                <div className="absolute top-3 right-3 bg-red-500/20 text-red-400 border border-red-500/30 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-widest shadow-lg">
                  BOSS
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div className="flex-1 space-y-6">
              <div>
                <motion.h1
                  initial={{ y: -20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  className="text-4xl md:text-6xl font-serif font-bold text-white mb-2 tracking-tight"
                >
                  {creature.name}
                </motion.h1>
                <div className="flex flex-wrap gap-3">
                  {creature.difficulty && (
                    <span className={`px-3 py-1 rounded-lg text-sm font-bold border ${creature.difficulty === 'Hard' ? 'bg-red-500/10 border-red-500/20 text-red-400' :
                      creature.difficulty === 'Medium' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                        'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      }`}>
                      {creature.difficulty}
                    </span>
                  )}
                  {creature.occurrence && (
                    <span className="px-3 py-1 rounded-lg text-sm font-medium bg-slate-800 text-slate-400 border border-slate-700">
                      {creature.occurrence}
                    </span>
                  )}
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: 'Hitpoints', value: formatNumber(creature.hitpoints), icon: Heart, color: 'text-rose-400' },
                  { label: 'Experience', value: formatNumber(creature.experience), icon: Star, color: 'text-amber-400' },
                  { label: 'Armor', value: creature.armor, icon: Shield, color: 'text-slate-200' },
                  { label: 'Speed', value: creature.speed, icon: Zap, color: 'text-yellow-200' },
                  { label: 'Max Damage', value: creature.max_damage || '?', icon: Swords, color: 'text-red-400' },
                  { label: 'Est. Exp/Hr', value: formatNumber(expPerHour), icon: '📈', color: 'text-emerald-400' },
                ].map((stat, i) => (
                  <div key={i} className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl flex items-center gap-4">
                    <div className={`p-2 rounded-lg bg-slate-950 ${stat.color}`}>
                      {typeof stat.icon === 'string' ? stat.icon : <stat.icon size={20} />}
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 uppercase font-bold tracking-wider">{stat.label}</div>
                      <div className={`text-xl font-bold font-mono ${stat.color}`}>{stat.value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 grid lg:grid-cols-12 gap-8">

        {/* Left Column: Details & Loot */}
        <div className="lg:col-span-8 space-y-8">

          {/* Behavior */}
          {creature.behavior && (
            <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 backdrop-blur">
              <h2 className="text-xl font-serif font-bold text-amber-500 mb-4 flex items-center gap-2">
                <Info size={20} /> Ecology & Strategy
              </h2>
              <p className="text-slate-300 leading-relaxed text-lg">
                {creature.behavior}
              </p>
            </div>
          )}

          {/* Loot Table */}
          <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 backdrop-blur">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-serif font-bold text-amber-500 flex items-center gap-2">
                <Gem size={20} /> Loot Table
              </h2>
              <div className="text-sm text-slate-500">
                Est. Profit: <span className="text-amber-400 font-mono">{formatNumber(profitPerHour)}</span> gp/hr
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {creature.loot_items.map((loot) => (
                <div key={loot.id} className="bg-slate-950/50 border border-slate-800 p-3 rounded-xl flex items-center justify-between group hover:border-slate-600 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg
                         ${loot.rarity === 'Rare' || loot.rarity === 'Very Rare' ? 'bg-amber-500/10 text-amber-500' : 'bg-slate-800 text-slate-500'}
                       `}>
                      💎
                    </div>
                    <div>
                      <div className="font-bold text-slate-200 group-hover:text-amber-400 transition-colors">{loot.item_name}</div>
                      <div className="text-xs text-slate-500">
                        {loot.percentage?.toFixed(2)}% drop chance
                      </div>
                    </div>
                  </div>
                  {loot.item_value && (
                    <div className="text-right">
                      <div className="font-mono text-amber-200">{formatNumber(loot.item_value)}</div>
                      <div className="text-[10px] text-slate-600 uppercase">Value</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Right Column: Spawns & Weaknesses */}
        <div className="lg:col-span-4 space-y-8">

          {/* Elements / Weaknesses */}
          <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 backdrop-blur">
            <h2 className="text-lg font-bold text-white mb-4">Elemental Sensitivity</h2>
            <div className="space-y-3">
              {(creature.weaknesses || []).map(w => (
                <div key={w.name} className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <span className="text-green-400 font-bold flex items-center gap-2">
                    <span className="text-xl">🔥</span> {w.name}
                  </span>
                  <span className="font-mono text-green-300">+20% Dmg</span>
                </div>
              ))}
              {(creature.resistances || []).map(r => (
                <div key={r.name} className="flex items-center justify-between p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <span className="text-red-400 font-bold flex items-center gap-2">
                    <span className="text-xl">🛡️</span> {r.name}
                  </span>
                  <span className="font-mono text-red-300">-20% Dmg</span>
                </div>
              ))}
              {(!creature.weaknesses?.length && !creature.resistances?.length) && (
                <div className="text-slate-500 text-sm italic py-2">No specific elemental strengths or weaknesses known.</div>
              )}
            </div>
          </div>

          {/* Spawn Locations */}
          {creature.spawn_locations.length > 0 && (
            <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 backdrop-blur">
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <MapPin className="text-amber-500" size={20} /> Known Habitats
              </h2>
              <div className="space-y-3">
                {creature.spawn_locations.map(spawn => (
                  spawn.hunt_zone && (
                    <Link
                      key={spawn.id}
                      to="/recommendations"
                      className="block p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-500/10 transition-all group"
                    >
                      <h4 className="font-bold text-slate-200 group-hover:text-amber-400 transition-colors mb-1">{spawn.hunt_zone.name}</h4>
                      <div className="flex items-center justify-between text-xs text-slate-500">
                        <span>Level {spawn.hunt_zone.min_level}+</span>
                        <span className="bg-slate-900 px-2 py-1 rounded text-slate-400 border border-slate-800 group-hover:border-amber-500/30 transition-colors">
                          {spawn.quantity || 'Unknown Qty'}
                        </span>
                      </div>
                    </Link>
                  )
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default CreatureDetailPage;
