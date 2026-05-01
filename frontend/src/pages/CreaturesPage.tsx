
import React, { useEffect, useState } from 'react';
import { creaturesApi, itemsApi, huntZonesApi } from '../services/api';
import { CreatureSimple, LootWithCreature, HuntZone } from '../types';
import CreatureCard from '../components/CreatureCard';
import TibiaMap from '../components/TibiaMap';
import { Search, Sword, Gem, MapPin, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';

type SearchMode = 'creatures' | 'items' | 'zones';

const CreaturesPage: React.FC = () => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<SearchMode>('creatures');
  const [searchTerm, setSearchTerm] = useState('');

  // Data
  const [creatures, setCreatures] = useState<CreatureSimple[]>([]);
  const [items, setItems] = useState<LootWithCreature[]>([]);
  const [zones, setZones] = useState<HuntZone[]>([]);

  // States
  const [loading, setLoading] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);

  // Debounce Search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm || !initialLoaded) {
        performSearch();
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm, mode]);

  const performSearch = async () => {
    setLoading(true);
    try {
      if (mode === 'creatures') {
        const data = await creaturesApi.getAll({
          search: searchTerm,
          limit: 100
        });
        setCreatures(data);
      } else if (mode === 'items') {
        if (searchTerm.length > 1) {
          const data = await itemsApi.search(searchTerm);
          setItems(data);
        } else {
          setItems([]);
        }
      } else if (mode === 'zones') {
        const data = await huntZonesApi.getAll({
          search: searchTerm,
          limit: 50
        });
        setZones(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setInitialLoaded(true);
    }
  };

  return (
    <div className="min-h-screen">

      {/* Hero Section */}
      <div className="relative py-12 md:py-20 text-center space-y-6">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-6xl font-serif font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-200 via-amber-400 to-amber-600 drop-shadow-[0_2px_10px_rgba(245,158,11,0.3)]"
        >
          {t('hero.title')}
        </motion.h1>
        
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="text-slate-300 text-sm md:text-base max-w-xl mx-auto px-4"
        >
          Buscador de mobs y items para completar tus Weekly Tasks más rápido
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="max-w-2xl mx-auto px-4 relative z-20"
        >
          {/* Search Bar Container */}
          <div className="bg-slate-900/80 backdrop-blur-xl border border-slate-700 rounded-2xl p-2 shadow-2xl flex flex-col md:flex-row gap-2">

            {/* Mode Toggle */}
            <div className="flex bg-slate-950 rounded-xl p-1 shrink-0 overflow-x-auto">
              <button
                onClick={() => setMode('creatures')}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${mode === 'creatures'
                  ? 'bg-amber-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
                  }`}
              >
                <Sword size={18} />
                <span className="hidden sm:inline">Monsters</span>
              </button>
              <button
                onClick={() => setMode('items')}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${mode === 'items'
                  ? 'bg-amber-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
                  }`}
              >
                <Gem size={18} />
                <span className="hidden sm:inline">Loot</span>
              </button>
              <button
                onClick={() => setMode('zones')}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${mode === 'zones'
                  ? 'bg-amber-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
                  }`}
              >
                <MapPin size={18} />
                <span className="hidden sm:inline">Zones</span>
              </button>
            </div>

            {/* Input */}
            <div className="flex-1 relative">
              <input
                type="text"
                placeholder={t('search.placeholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full h-full bg-slate-800/50 rounded-xl pl-12 pr-4 text-white placeholder-slate-500 outline-none focus:bg-slate-800 transition-colors"
              />
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={20} />
            </div>

          </div>
        </motion.div>
      </div>

      {/* Content Grid */}
      <div className="container mx-auto px-4 pb-20">

        {loading && (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-amber-500" size={48} />
          </div>
        )}

        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">

            {/* CREATURES */}
            {mode === 'creatures' && creatures.map((creature, idx) => (
              <CreatureCard key={creature.id} creature={creature} index={idx} />
            ))}

            {/* ITEMS */}
            {mode === 'items' && items.map((item, idx) => (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                key={`${item.id}-${idx}`}
                className="bg-slate-900/50 border border-slate-700/50 p-6 rounded-xl relative overflow-hidden group hover:border-amber-500/30 transition-all"
              >
                <div className="absolute top-0 right-0 p-4 opacity-50 font-serif font-bold text-6xl text-slate-800 group-hover:text-amber-500/10 transition-colors">
                  {item.percentage}%
                </div>
                <h3 className="text-xl font-bold text-amber-100 mb-1">{item.item_name}</h3>
                <div className="flex items-center gap-2 mb-4">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${item.rarity === 'Rare' ? 'bg-purple-500/20 text-purple-300' : 'bg-slate-700 text-slate-300'}`}>
                    {item.rarity}
                  </span>
                  <span className="text-xs text-slate-400">Value: {item.item_value}gp</span>
                </div>

                <div className="pt-4 border-t border-slate-800">
                  <div className="text-xs text-slate-500 uppercase font-bold mb-2">Dropped By</div>
                  <div className="flex items-center gap-2">
                    {item.creature && (
                      <CreatureCard creature={item.creature} index={0} />
                    )}
                  </div>
                </div>
              </motion.div>
            ))}

            {/* ZONES */}
            {mode === 'zones' && zones.map((zone) => (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                key={zone.id}
                className="bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden group hover:border-amber-500/30 transition-all"
              >
                {/* Map Miniature - Click to expand logic would be here */}
                <div className="bg-slate-950 h-40 relative group-hover:brightness-110 transition-all">
                  {/* Render a map centered on the zone if coords exist */}
                  <TibiaMap
                    zoom={11}
                    center={zone.location_x ? { x: zone.location_x, y: zone.location_y! } : undefined}
                    markers={zone.location_x ? [{ x: zone.location_x, y: zone.location_y!, label: zone.name }] : []}
                  />
                  {/* Overlay to prevent interaction in card mode */}
                  <div className="absolute inset-0 bg-transparent" />
                </div>

                <div className="p-6">
                  <h3 className="text-xl font-bold text-amber-100 mb-1">{zone.name}</h3>
                  <div className="flex gap-2 mb-4">
                    <span className="text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded">{zone.city || 'Wilderness'}</span>
                    <span className="text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded">Lvl {zone.min_level}+</span>
                  </div>
                  <div className="text-sm text-slate-400">
                    {zone.difficulty} difficulty
                  </div>
                </div>
              </motion.div>
            ))}

          </div>
        )}

        {!loading && creatures.length === 0 && items.length === 0 && zones.length === 0 && (
          <div className="text-center py-20 opacity-50">
            <div className="text-6xl mb-4">📜</div>
            <p className="font-serif text-xl">Bestiary is empty... or creature is hiding.</p>
          </div>
        )}

      </div>
    </div>
  );
};

export default CreaturesPage;
