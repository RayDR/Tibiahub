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
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';

// Vocation Config
const VOCATIONS = [
  { id: 'knight', label: 'Knight', icon: Shield, color: 'text-primary', bg: 'bg-primary/10' },
  { id: 'paladin', label: 'Paladin', icon: Swords, color: 'text-success', bg: 'bg-success/10' },
  { id: 'sorcerer', label: 'Sorcerer', icon: Zap, color: 'text-accent', bg: 'bg-accent/10' },
  { id: 'druid', label: 'Druid', icon: Sparkles, color: 'text-info', bg: 'bg-info/10' },
  { id: 'monk', label: 'Monk', icon: Scroll, color: 'text-danger', bg: 'bg-danger/10' },
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
  const { isAuthenticated } = useAuth();

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

      if (isAuthenticated) {
        void activityApi.record({
          activity_type: 'hunt_search',
          entity_type: mode,
          query: mode === 'solo' ? `${soloVocation}:${soloLevel}` : `party:${party.length}`,
          metadata: {
            mode,
            goal,
            solo_vocation: soloVocation,
            solo_level: soloLevel,
            party_size: party.length,
          },
        }).catch(() => {
          // Non-blocking history event.
        });
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
      if (isAuthenticated) {
        void activityApi.record({
          activity_type: 'view_zone',
          entity_type: 'zone',
          entity_id: String(recommendation.zone_id),
          metadata: {
            name: recommendation.zone_name,
          },
        }).catch(() => {
          // Non-blocking history event.
        });
      }
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
    <div className="pb-12 pt-6">

      {/* Hero Section */}
      <div className="mb-8 text-center">
        <PageHeader
          title="Hunt Finder"
          subtitle="Advanced recommendations based on vocation synergy, levels and loot efficiency."
          icon={faCompass}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-12">

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
              <h2 className="text-xl font-bold text-content-primary flex items-center gap-2">
                {mode === 'solo' ? <User className="text-primary" /> : <Users className="text-primary" />}
                {mode === 'solo' ? 'Configuration' : 'Team Composition'}
              </h2>
            </div>

            {mode === 'solo' ? (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-content-muted uppercase font-bold mb-2 block">Vocation</label>
                  <div className="grid grid-cols-5 gap-2">
                    {VOCATIONS.map(v => (
                      <button
                        key={v.id}
                        onClick={() => setSoloVocation(v.id)}
                        className={`aspect-square rounded-xl border flex flex-col items-center justify-center gap-1 transition-all ${soloVocation === v.id
                          ? `bg-primary/20 border-primary ${v.color}`
                          : 'bg-surface border-line text-content-muted hover:border-line'
                          }`}
                        title={v.label}
                      >
                        <v.icon size={20} />
                      </button>
                    ))}
                  </div>
                  <div className="text-center mt-2 text-sm font-bold text-primary">
                    {VOCATIONS.find(v => v.id === soloVocation)?.label}
                  </div>
                </div>

                <div>
                  <label className="text-xs text-content-muted uppercase font-bold mb-2 block">Level</label>
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
                      className="bg-surface-base/50 border border-line rounded-xl p-3 flex gap-2 items-center group"
                    >
                      <div className="w-8 h-8 rounded-lg bg-surface-base flex items-center justify-center text-content-muted font-mono text-xs">
                        {idx + 1}
                      </div>

                      <div className="flex-1">
                        <select
                          value={member.vocation}
                          onChange={(e) => updateMember(member.id, 'vocation', e.target.value)}
                          className="w-full bg-transparent border-none text-sm text-content-primary focus:ring-0 cursor-pointer"
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
                          className="w-full bg-surface-base border border-line rounded px-2 py-1 text-xs text-right text-content-primary focus:border-primary outline-none"
                        />
                      </div>

                      <button
                        onClick={() => removeMember(member.id)}
                        disabled={party.length <= 1}
                        className="p-2 text-content-muted hover:text-danger disabled:opacity-0 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {party.length < 4 && (
                  <button
                    onClick={addMember}
                    className="w-full py-3 border border-dashed border-line rounded-xl text-content-muted hover:text-primary hover:border-primary/50 hover:bg-primary/5 transition-all text-sm font-bold flex items-center justify-center gap-2"
                  >
                    <Plus size={16} /> Add Party Member
                  </button>
                )}
              </div>
            )}

            <div className="mt-6 pt-6 border-t border-line">
              <label className="text-xs text-content-muted uppercase font-bold mb-2 block">Optimization Goal</label>
              <div className="grid grid-cols-3 gap-2 mb-6">
                {(['exp', 'profit', 'balanced'] as const).map(g => (
                  <button
                    key={g}
                    onClick={() => setGoal(g)}
                    className={`py-2 rounded-lg text-xs font-bold uppercase transition-all border ${goal === g
                      ? 'bg-primary/20 border-primary text-primary'
                      : 'bg-surface-base border-line text-content-muted hover:border-line'
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

                  <div className="mt-6 p-4 bg-surface-base/50 rounded-xl border border-dashed border-line">
                    <h3 className="text-sm font-bold text-content-secondary mb-2 flex items-center gap-2">
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
                          <span className="text-content-muted text-xs">Based on {uniqueVocations} unique vocs</span>
                          <span className="text-xl font-bold text-success">+{bonus}% EXP</span>
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
            <div className="h-full flex flex-col items-center justify-center text-content-muted border-2 border-dashed border-line rounded-3xl min-h-[400px]">
              <Map size={64} className="mb-4 opacity-20" />
              <p className="text-lg">Configure your hunt to see recommendations</p>
            </div>
          )}

          {loading && (
            <div className="h-full flex flex-col items-center justify-center text-primary min-h-[400px]">
              <Map size={42} className="mb-4 animate-pulse" />
              <p className="font-serif text-lg">Scouting optimal locations...</p>
            </div>
          )}

          {recommendations && (
            <div className="space-y-6">

              {/* Stats Summary */}
              {!recommendations.is_solo && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-surface-base/50 border border-line p-4 rounded-xl">
                    <div className="text-content-muted text-xs uppercase font-bold mb-1">Avg Level</div>
                    <div className="text-2xl font-mono font-bold text-content-primary">{Math.round(recommendations.avg_level)}</div>
                  </div>
                  <div className="bg-surface-base/50 border border-line p-4 rounded-xl">
                    <div className="text-content-muted text-xs uppercase font-bold mb-1">Team Size</div>
                    <div className="text-2xl font-mono font-bold text-content-primary">{recommendations.party_size}</div>
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
                    className="group bg-surface-base/80 border border-line hover:border-primary/50 rounded-2xl p-6 backdrop-blur transition-all hover:shadow-xl hover:shadow-surface-base/50"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-2xl font-serif font-bold text-content-primary group-hover:text-primary transition-colors">
                          {rec.zone_name}
                        </h3>
                        <div className="flex gap-2 mt-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold border ${REC_COLORS[rec.difficulty ?? ''] || 'bg-surface text-content-secondary border-line'}`}>
                            {rec.difficulty}
                          </span>
                          <span className="px-2 py-0.5 rounded text-xs font-bold bg-surface-base text-content-secondary border border-line">
                            Lvl {rec.min_level}+
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-bold text-primary">{Math.round(rec.score)}</div>
                        <div className="text-xs text-content-muted uppercase font-bold">Match Score</div>
                      </div>
                    </div>

                    <div className="mb-4 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border border-line bg-surface-base/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-content-muted">Estimated Exp</div>
                        <div className="text-sm font-semibold text-success">{formatRate(rec.estimated_exp_hour)}</div>
                      </div>
                      <div className="rounded-lg border border-line bg-surface-base/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-content-muted">Estimated Profit</div>
                        <div className="text-sm font-semibold text-primary">{formatRate(rec.estimated_profit_hour)}</div>
                      </div>
                      <div className="rounded-lg border border-line bg-surface-base/60 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wide text-content-muted">Access</div>
                        <div className="text-sm font-semibold text-content-primary">{rec.requires_premium ? 'Premium' : 'Free Access'}</div>
                      </div>
                    </div>

                    {/* Reasons */}
                    <div className="flex flex-wrap gap-2 mb-4">
                      {rec.reasons?.map((reason: string, idx: number) => (
                        <span key={idx} className="bg-surface text-content-secondary text-xs px-2 py-1 rounded-md flex items-center gap-1">
                          <TrendingUp size={12} className="text-success" /> {reason}
                        </span>
                      ))}
                      {(rec.synergy_bonus ?? 1) > 1 && (
                        <span className="bg-accent/10 text-accent border border-accent/20 text-xs px-2 py-1 rounded-md flex items-center gap-1">
                          <Sparkles size={12} /> Synergy +{Math.round(((rec.synergy_bonus ?? 1) - 1) * 100)}%
                        </span>
                      )}
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={() => void inspectZone(rec)}
                        className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface-base/60 px-3 py-2 text-xs font-semibold text-content-primary hover:border-primary/60 hover:text-primary"
                      >
                        <Eye size={14} /> Inspect Zone
                      </button>
                    </div>

                  </motion.div>
                ))}

                {recommendations.recommendations?.length === 0 && (
                  <div className="text-center py-12 text-content-muted">
                    No suitable hunt zones found for this configuration. Try adjusting levels or team composition.
                  </div>
                )}
              </div>
            </div>
          )}

          {(zoneLoading || selectedZone || selectedRecommendation) && (
            <div className="mt-6 rounded-2xl border border-line bg-surface-base/80 p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-content-primary">Zone Inspector</h3>
                <button
                  onClick={() => {
                    setSelectedZone(null);
                    setSelectedRecommendation(null);
                  }}
                  className="rounded-md border border-line p-1.5 text-content-secondary hover:text-content-primary"
                >
                  <X size={14} />
                </button>
              </div>

              {zoneLoading && (
                <div className="rounded-xl border border-line bg-surface-base/60 p-6 text-sm text-content-secondary">
                  Loading zone details...
                </div>
              )}

              {!zoneLoading && selectedRecommendation && (
                <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-line bg-surface-base/60 p-4">
                      <div className="mb-2 text-xs uppercase tracking-wider text-content-muted">Recommended Zone</div>
                      <div className="text-xl font-bold text-primary">{selectedRecommendation.zone_name}</div>
                      <div className="mt-2 text-sm text-content-secondary">
                        Level {selectedRecommendation.min_level ?? 'N/A'}
                        {selectedRecommendation.max_level ? ` - ${selectedRecommendation.max_level}` : '+'}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedRecommendation.requires_premium && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-1 text-[11px] font-semibold text-primary">
                            <Crown size={12} /> Premium
                          </span>
                        )}
                        {selectedRecommendation.difficulty && (
                          <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${REC_COLORS[selectedRecommendation.difficulty] || 'bg-surface text-content-secondary border-line'}`}>
                            {selectedRecommendation.difficulty}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-line bg-surface-base/60 p-4">
                      <div className="mb-2 text-xs uppercase tracking-wider text-content-muted">Expected Rates</div>
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between rounded-lg border border-line bg-surface-base px-3 py-2">
                          <span className="text-content-secondary">EXP</span>
                          <span className="font-semibold text-success">{formatRate(selectedRecommendation.estimated_exp_hour)}</span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg border border-line bg-surface-base px-3 py-2">
                          <span className="flex items-center gap-1 text-content-secondary"><Coins size={13} /> Profit</span>
                          <span className="font-semibold text-primary">{formatRate(selectedRecommendation.estimated_profit_hour)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {selectedZone && (
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-line bg-surface-base/60 p-4">
                        <div className="mb-2 text-xs uppercase tracking-wider text-content-muted">Route & Notes</div>
                        <div className="text-sm text-content-secondary">
                          <div>City: <span className="text-content-primary">{selectedZone.city || 'Unknown'}</span></div>
                          <div className="mt-1">Size: <span className="text-content-primary">{selectedZone.size || 'Unknown'}</span></div>
                          {selectedZone.requires_quest && (
                            <div className="mt-1 text-primary">Quest required: {selectedZone.quest_name || 'Yes'}</div>
                          )}
                        </div>
                        {selectedZone.description && (
                          <p className="mt-3 text-xs leading-relaxed text-content-secondary">{selectedZone.description}</p>
                        )}
                        {selectedZone.tips && (
                          <p className="mt-3 rounded-lg border border-line bg-surface-base px-3 py-2 text-xs leading-relaxed text-info">
                            Tip: {selectedZone.tips}
                          </p>
                        )}
                      </div>

                      <div className="rounded-xl border border-line bg-surface-base/60 p-4">
                        <div className="mb-2 text-xs uppercase tracking-wider text-content-muted">Map Context</div>
                        {selectedZone.map_image_url && !mapPreviewFailed ? (
                          <img
                            src={huntZonesApi.getMapImageUrl(selectedZone.id)}
                            alt={selectedZone.name}
                            className="h-40 w-full rounded-lg border border-line object-cover"
                            loading="lazy"
                            onError={() => setMapPreviewFailed(true)}
                          />
                        ) : (
                          <div className="h-40 overflow-hidden rounded-lg border border-line bg-surface-base">
                            <TibiaMap
                              zoom={11}
                              center={selectedZone.location_x ? { x: selectedZone.location_x, y: selectedZone.location_y! } : undefined}
                              markers={selectedZone.location_x ? [{ x: selectedZone.location_x, y: selectedZone.location_y!, label: selectedZone.name }] : []}
                            />
                          </div>
                        )}
                        <div className="mt-3 text-xs text-content-secondary">
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
  'Trivial': 'bg-surface-hover/10 text-content-secondary border-line/20',
  'Easy': 'bg-success/10 text-success border-success/20',
  'Medium': 'bg-info/10 text-info border-info/20',
  'Hard': 'bg-primary/10 text-primary border-primary/20',
  'Extreme': 'bg-danger/10 text-danger border-danger/20',
};

export default HuntRecommendationsPage;
