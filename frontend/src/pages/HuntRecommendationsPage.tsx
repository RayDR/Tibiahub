import React, { useState } from 'react';
import { huntZonesApi } from '../services/api';
import { Plus, Trash2, Users, Map, Swords, TrendingUp, User, Shield, Zap, Sparkles, Scroll, Eye, X, Crown, Coins } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { HuntZone } from '../types';
import TibiaMap from '../components/TibiaMap';
import { faCompass } from '@fortawesome/free-solid-svg-icons';
import PageHeader from '../components/ui/PageHeader';
import AppTabs from '../components/ui/AppTabs';
import AppButton from '../components/ui/AppButton';
import AppCard from '../components/ui/AppCard';
import AppInput from '../components/ui/AppInput';

// Vocation Config
const VOCATIONS = [
  { id: 'knight', label: 'Knight', icon: Shield, color: 'text-amber-600', bg: 'bg-amber-600/10' },
  { id: 'paladin', label: 'Paladin', icon: Swords, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'sorcerer', label: 'Sorcerer', icon: Zap, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  { id: 'druid', label: 'Druid', icon: Sparkles, color: 'text-sky-500', bg: 'bg-sky-500/10' },
  { id: 'monk', label: 'Monk', icon: Scroll, color: 'text-rose-500', bg: 'bg-rose-500/10' },
];

interface PartyMember {
  id: number;
  vocation: string;
  level: number;
}

interface RecommendationItem {
  zone_id: number;
  zone_name: string;
  score: number;
  reasons?: string[];
  synergy_bonus?: number;
  min_level?: number;
  max_level?: number;
  difficulty?: string;
  estimated_exp_hour?: number;
  estimated_profit_hour?: number;
  requires_premium?: boolean;
}

const HuntRecommendationsPage: React.FC = () => {
  const [mode, setMode] = useState<'solo' | 'party'>('solo');

  // Solo State
  const [soloVocation, setSoloVocation] = useState('knight');
  const [soloLevel, setSoloLevel] = useState(100);

  // Party State
  const [party, setParty] = useState<PartyMember[]>([
    { id: 1, vocation: 'knight', level: 100 }
  ]);

  const [recommendations, setRecommendations] = useState<any | null>(null);
  const [selectedZone, setSelectedZone] = useState<HuntZone | null>(null);
  const [selectedRecommendation, setSelectedRecommendation] = useState<RecommendationItem | null>(null);
  const [zoneLoading, setZoneLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [goal, setGoal] = useState<'exp' | 'profit' | 'balanced'>('exp');
  const [mapPreviewFailed, setMapPreviewFailed] = useState(false);

  // Handlers
  const addMember = () => {
    if (party.length >= 4) return;
    setParty([...party, { id: Date.now(), vocation: 'druid', level: 100 }]);
  };

  const removeMember = (id: number) => {
    if (party.length <= 1) return;
    setParty(party.filter(m => m.id !== id));
  };

  const updateMember = (id: number, field: 'vocation' | 'level', value: any) => {
    setParty(party.map(m => m.id === id ? { ...m, [field]: value } : m));
  };

  const findSpots = async () => {
    setLoading(true);
    setRecommendations(null);
    setSelectedZone(null);
    setSelectedRecommendation(null);
    try {
      if (mode === 'solo') {
        const data = await huntZonesApi.getRecommendations(soloVocation as any, soloLevel, 10);
        // Transform the list response to match the "recommendations" object structure for consistent rendering
        setRecommendations({
          recommendations: data.map(rec => ({
            zone_id: rec.zone.id,
            zone_name: rec.zone.name,
            score: rec.score,
            reasons: rec.reasons,
            min_level: rec.zone.min_level,
            difficulty: rec.zone.difficulty || 'Medium'
          })),
          is_solo: true
        });
      } else {
        const payload = party.map(m => ({ vocation: m.vocation, level: Number(m.level) }));
        const data = await huntZonesApi.getPartyRecommendations(payload, goal);
        setRecommendations(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const inspectZone = async (recommendation: RecommendationItem) => {
    setSelectedRecommendation(recommendation);
    setMapPreviewFailed(false);
    setZoneLoading(true);
    try {
      const zone = await huntZonesApi.getById(recommendation.zone_id);
      setSelectedZone(zone);
    } catch (error) {
      console.error('Failed to load zone details', error);
      setSelectedZone(null);
    } finally {
      setZoneLoading(false);
    }
  };

  const formatRate = (value?: number) => {
    if (!value) return 'N/A';
    return `${value.toLocaleString()}/h`;
  };

  return (
    <div className="min-h-screen pb-20 pt-24">

      {/* Hero Section */}
      <div className="container mx-auto px-4 mb-12 text-center">
        <PageHeader
          title="Hunt Finder"
          subtitle="Advanced recommendations based on vocation synergy, levels and loot efficiency."
          icon={faCompass}
        />
      </div>

      <div className="container mx-auto px-4 grid lg:grid-cols-12 gap-8">

        {/* Configuration Panel */}
        <div className="lg:col-span-4 space-y-6">

          {/* Mode Switch */}
          <AppTabs
            activeKey={mode}
            onChange={(key) => {
              setMode(key as 'solo' | 'party');
              setRecommendations(null);
            }}
            items={[
              { key: 'solo', label: 'Solo Hunt' },
              { key: 'party', label: 'Party Team' },
            ]}
          />

          <AppCard className="p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                {mode === 'solo' ? <User className="text-amber-500" /> : <Users className="text-amber-500" />}
                {mode === 'solo' ? 'Configuration' : 'Team Composition'}
              </h2>
            </div>

            {mode === 'solo' ? (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">Vocation</label>
                  <div className="grid grid-cols-5 gap-2">
                    {VOCATIONS.map(v => (
                      <button
                        key={v.id}
                        onClick={() => setSoloVocation(v.id)}
                        className={`aspect-square rounded-xl border flex flex-col items-center justify-center gap-1 transition-all ${soloVocation === v.id
                          ? `bg-amber-500/20 border-amber-500 ${v.color}`
                          : 'bg-slate-800 border-slate-700 text-slate-500 hover:border-slate-600'
                          }`}
                        title={v.label}
                      >
                        <v.icon size={20} />
                      </button>
                    ))}
                  </div>
                  <div className="text-center mt-2 text-sm font-bold text-amber-500">
                    {VOCATIONS.find(v => v.id === soloVocation)?.label}
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">Level</label>
                  <AppInput
                    type="number"
                    value={soloLevel}
                    onChange={(e) => setSoloLevel(Number(e.target.value))}
                    className="font-mono text-lg"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <AnimatePresence>
                  {party.map((member, idx) => (
                    <motion.div
                      key={member.id}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="bg-slate-950/50 border border-slate-800 rounded-xl p-3 flex gap-2 items-center group"
                    >
                      <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-slate-500 font-mono text-xs">
                        {idx + 1}
                      </div>

                      <div className="flex-1">
                        <select
                          value={member.vocation}
                          onChange={(e) => updateMember(member.id, 'vocation', e.target.value)}
                          className="w-full bg-transparent border-none text-sm text-slate-200 focus:ring-0 cursor-pointer"
                        >
                          {VOCATIONS.map(v => (
                            <option key={v.id} value={v.id}>{v.label}</option>
                          ))}
                        </select>
                      </div>

                      <div className="w-20">
                        <input
                          type="number"
                          value={member.level}
                          onChange={(e) => updateMember(member.id, 'level', e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-right text-white focus:border-amber-500 outline-none"
                        />
                      </div>

                      <button
                        onClick={() => removeMember(member.id)}
                        disabled={party.length <= 1}
                        className="p-2 text-slate-600 hover:text-red-400 disabled:opacity-0 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {party.length < 4 && (
                  <button
                    onClick={addMember}
                    className="w-full py-3 border border-dashed border-slate-700 rounded-xl text-slate-500 hover:text-amber-500 hover:border-amber-500/50 hover:bg-amber-500/5 transition-all text-sm font-bold flex items-center justify-center gap-2"
                  >
                    <Plus size={16} /> Add Party Member
                  </button>
                )}
              </div>
            )}

            <div className="mt-6 pt-6 border-t border-slate-800">
              <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">Optimization Goal</label>
              <div className="grid grid-cols-3 gap-2 mb-6">
                {(['exp', 'profit', 'balanced'] as const).map(g => (
                  <button
                    key={g}
                    onClick={() => setGoal(g)}
                    className={`py-2 rounded-lg text-xs font-bold uppercase transition-all border ${goal === g
                      ? 'bg-amber-500/20 border-amber-500 text-amber-500'
                      : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-600'
                      }`}
                  >
                    {g}
                  </button>
                ))}
              </div>

              {mode === 'party' && (
                <>
                  <AppButton
                    onClick={addMember}
                    disabled={party.length >= 4}
                    variant="ghost"
                    className="w-full border-2 border-dashed text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus size={16} /> Add Party Member
                  </AppButton>

                  <div className="mt-6 p-4 bg-slate-950/50 rounded-xl border border-dashed border-slate-700">
                    <h3 className="text-sm font-bold text-slate-400 mb-2 flex items-center gap-2">
                      <TrendingUp size={16} /> Estimated Bonus
                    </h3>
                    {(() => {
                      const uniqueVocations = new Set(party.map(p => p.vocation)).size;
                      const count = party.length;
                      let bonus = 0;
                      if (count >= 1) bonus = 20;
                      if (uniqueVocations >= 2) bonus = 30;
                      if (uniqueVocations >= 3) bonus = 60;
                      if (uniqueVocations >= 4) bonus = 100;

                      return (
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500 text-xs">Based on {uniqueVocations} unique vocs</span>
                          <span className="text-xl font-bold text-green-400">+{bonus}% EXP</span>
                        </div>
                      )
                    })()}
                  </div>
                </>
              )}

              <AppButton
                onClick={findSpots}
                disabled={loading}
                className="w-full h-14 inline-flex items-center justify-center gap-2"
              >
                {loading ? <div className="animate-spin">...</div> : <Map size={20} />}
                Find Hunting Spots
              </AppButton>
            </div>
          </AppCard>
        </div>

        {/* Results Area */}
        <div className="lg:col-span-8">
          {!recommendations && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 border-2 border-dashed border-slate-800 rounded-3xl min-h-[400px]">
              <Map size={64} className="mb-4 opacity-20" />
              <p className="text-lg">Configure your hunt to see recommendations</p>
            </div>
          )}

          {loading && (
            <div className="h-full flex flex-col items-center justify-center text-amber-500 min-h-[400px]">
              <Map size={42} className="mb-4 animate-pulse" />
              <p className="font-serif text-lg">Scouting optimal locations...</p>
            </div>
          )}

          {recommendations && (
            <div className="space-y-6">

              {/* Stats Summary */}
              {!recommendations.is_solo && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                    <div className="text-slate-500 text-xs uppercase font-bold mb-1">Avg Level</div>
                    <div className="text-2xl font-mono font-bold text-white">{Math.round(recommendations.avg_level)}</div>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                    <div className="text-slate-500 text-xs uppercase font-bold mb-1">Team Size</div>
                    <div className="text-2xl font-mono font-bold text-white">{recommendations.party_size}</div>
                  </div>
                </div>
              )}

              {/* List */}
              <div className="space-y-4">
                {recommendations.recommendations?.map((rec: RecommendationItem, i: number) => (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    key={rec.zone_id}
                    className="group bg-slate-900/80 border border-slate-700 hover:border-amber-500/50 rounded-2xl p-6 backdrop-blur transition-all hover:shadow-xl hover:shadow-black/50"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-2xl font-serif font-bold text-white group-hover:text-amber-400 transition-colors">
                          {rec.zone_name}
                        </h3>
                        <div className="flex gap-2 mt-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold border ${REC_COLORS[rec.difficulty] || 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                            {rec.difficulty}
                          </span>
                          <span className="px-2 py-0.5 rounded text-xs font-bold bg-slate-950 text-slate-400 border border-slate-800">
                            Lvl {rec.min_level}+
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-bold text-amber-500">{Math.round(rec.score)}</div>
                        <div className="text-xs text-slate-500 uppercase font-bold">Match Score</div>
                      </div>
                    </div>

                    <div className="mb-4 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-slate-500">Estimated Exp</div>
                        <div className="text-sm font-semibold text-emerald-300">{formatRate(rec.estimated_exp_hour)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-slate-500">Estimated Profit</div>
                        <div className="text-sm font-semibold text-amber-300">{formatRate(rec.estimated_profit_hour)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-slate-500">Access</div>
                        <div className="text-sm font-semibold text-slate-200">{rec.requires_premium ? 'Premium' : 'Free Access'}</div>
                      </div>
                    </div>

                    {/* Reasons */}
                    <div className="flex flex-wrap gap-2 mb-4">
                      {rec.reasons?.map((reason: string, idx: number) => (
                        <span key={idx} className="bg-slate-800 text-slate-300 text-xs px-2 py-1 rounded-md flex items-center gap-1">
                          <TrendingUp size={12} className="text-emerald-500" /> {reason}
                        </span>
                      ))}
                      {(rec.synergy_bonus ?? 1) > 1 && (
                        <span className="bg-purple-500/10 text-purple-400 border border-purple-500/20 text-xs px-2 py-1 rounded-md flex items-center gap-1">
                          <Sparkles size={12} /> Synergy +{Math.round((rec.synergy_bonus - 1) * 100)}%
                        </span>
                      )}
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={() => void inspectZone(rec)}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-amber-500/60 hover:text-amber-300"
                      >
                        <Eye size={14} /> Inspect Zone
                      </button>
                    </div>

                  </motion.div>
                ))}

                {recommendations.recommendations?.length === 0 && (
                  <div className="text-center py-12 text-slate-500">
                    No suitable hunt zones found for this configuration. Try adjusting levels or team composition.
                  </div>
                )}
              </div>
            </div>
          )}

          {(zoneLoading || selectedZone || selectedRecommendation) && (
            <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/80 p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-100">Zone Inspector</h3>
                <button
                  onClick={() => {
                    setSelectedZone(null);
                    setSelectedRecommendation(null);
                  }}
                  className="rounded-md border border-slate-700 p-1.5 text-slate-400 hover:text-slate-200"
                >
                  <X size={14} />
                </button>
              </div>

              {zoneLoading && (
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
                  Loading zone details...
                </div>
              )}

              {!zoneLoading && selectedRecommendation && (
                <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                      <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Recommended Zone</div>
                      <div className="text-xl font-bold text-amber-300">{selectedRecommendation.zone_name}</div>
                      <div className="mt-2 text-sm text-slate-400">
                        Level {selectedRecommendation.min_level ?? 'N/A'}
                        {selectedRecommendation.max_level ? ` - ${selectedRecommendation.max_level}` : '+'}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedRecommendation.requires_premium && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] font-semibold text-amber-300">
                            <Crown size={12} /> Premium
                          </span>
                        )}
                        {selectedRecommendation.difficulty && (
                          <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${REC_COLORS[selectedRecommendation.difficulty] || 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                            {selectedRecommendation.difficulty}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                      <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Expected Rates</div>
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900 px-3 py-2">
                          <span className="text-slate-400">EXP</span>
                          <span className="font-semibold text-emerald-300">{formatRate(selectedRecommendation.estimated_exp_hour)}</span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900 px-3 py-2">
                          <span className="flex items-center gap-1 text-slate-400"><Coins size={13} /> Profit</span>
                          <span className="font-semibold text-amber-300">{formatRate(selectedRecommendation.estimated_profit_hour)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {selectedZone && (
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Route & Notes</div>
                        <div className="text-sm text-slate-300">
                          <div>City: <span className="text-slate-100">{selectedZone.city || 'Unknown'}</span></div>
                          <div className="mt-1">Size: <span className="text-slate-100">{selectedZone.size || 'Unknown'}</span></div>
                          {selectedZone.requires_quest && (
                            <div className="mt-1 text-amber-300">Quest required: {selectedZone.quest_name || 'Yes'}</div>
                          )}
                        </div>
                        {selectedZone.description && (
                          <p className="mt-3 text-xs leading-relaxed text-slate-400">{selectedZone.description}</p>
                        )}
                        {selectedZone.tips && (
                          <p className="mt-3 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs leading-relaxed text-cyan-300">
                            Tip: {selectedZone.tips}
                          </p>
                        )}
                      </div>

                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Map Context</div>
                        {selectedZone.map_image_url && !mapPreviewFailed ? (
                          <img
                            src={huntZonesApi.getMapImageUrl(selectedZone.id)}
                            alt={selectedZone.name}
                            className="h-40 w-full rounded-lg border border-slate-800 object-cover"
                            loading="lazy"
                            onError={() => setMapPreviewFailed(true)}
                          />
                        ) : (
                          <div className="h-40 overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
                            <TibiaMap
                              zoom={11}
                              center={selectedZone.location_x ? { x: selectedZone.location_x, y: selectedZone.location_y! } : undefined}
                              markers={selectedZone.location_x ? [{ x: selectedZone.location_x, y: selectedZone.location_y!, label: selectedZone.name }] : []}
                            />
                          </div>
                        )}
                        <div className="mt-3 text-xs text-slate-400">
                          Coordinates: {selectedZone.location_x ?? 'N/A'}, {selectedZone.location_y ?? 'N/A'}, {selectedZone.location_z ?? 'N/A'}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Helper for colors
const REC_COLORS: Record<string, string> = {
  'Trivial': 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  'Easy': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  'Medium': 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  'Hard': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  'Extreme': 'bg-red-500/10 text-red-400 border-red-500/20',
};

export default HuntRecommendationsPage;
