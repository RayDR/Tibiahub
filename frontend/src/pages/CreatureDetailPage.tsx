import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowLeft, Gem, Heart, Info, Loader2, MapPin, Shield, Skull, Swords, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import LootDisplay from '../components/LootDisplay';
import ImageWithFallback from '../components/ImageWithFallback';
import type { Creature } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';

const formatNumber = (value?: number | null): string => {
  if (value === null || value === undefined) return 'Unknown';
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return `${value}`;
};

const CreatureDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [creature, setCreature] = useState<Creature | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showFullOverview, setShowFullOverview] = useState(false);
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    const fetchCreature = async () => {
      if (!slug) return;
      try {
        setLoading(true);
        setErrorMessage(null);
        const response = await fetch(`/api/v1/creatures/${encodeURIComponent(slug)}`);
        if (!response.ok) {
          throw new Error("We couldn't find this creature.");
        }
        const data = await response.json();
        setCreature(data);

        if (isAuthenticated && data?.id) {
          void activityApi.record({
            activity_type: data.is_boss ? 'view_boss' : 'view_creature',
            entity_type: 'creature',
            entity_id: String(data.id),
            metadata: {
              name: data.name,
              slug: data.slug,
              is_boss: !!data.is_boss,
            },
          }).catch(() => {
            // Non-blocking history event.
          });
        }

        const canonicalSlug = response.headers.get('x-canonical-slug') || data.slug;

        try {
          const current = JSON.parse(localStorage.getItem('recentCreatures') || '[]') as Array<{
            id: number;
            slug?: string;
            name: string;
            image_url?: string;
            viewed_at: string;
          }>;
          const deduped = current.filter((entry) => entry.id !== data.id);
          const updated = [
            {
              id: data.id,
              slug: data.slug,
              name: data.name,
              image_url: data.image_url,
              viewed_at: new Date().toISOString(),
            },
            ...deduped,
          ].slice(0, 20);
          localStorage.setItem('recentCreatures', JSON.stringify(updated));
        } catch {
          // ignore storage errors
        }

        if (canonicalSlug && canonicalSlug !== slug) {
          navigate(`/creatures/${canonicalSlug}`, { replace: true });
        }
      } catch (error: any) {
        console.error('Failed to load creature details', error);
        setErrorMessage("We couldn't find this creature.");
      } finally {
        setLoading(false);
      }
    };
    void fetchCreature();
  }, [slug, navigate, isAuthenticated]);

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

  const overview = creature.description || 'Not available';
  const overviewNeedsToggle = overview.length > 300;
  const overviewText = showFullOverview ? overview : `${overview.slice(0, 300)}${overviewNeedsToggle ? '...' : ''}`;
  const accessRequirements = (creature.related_tasks || []).filter((task) => /quest|mission|access|required/i.test(task));
  const displayRequirements = accessRequirements.length > 0 ? accessRequirements : (creature.related_tasks || []);

  const backTarget = (location.state as { from?: string } | null)?.from;

  return (
    <div className="min-h-screen pb-20 pt-28">
      <div className="relative mb-8">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-amber-500/10 to-transparent" />
        <div className="container relative z-10 mx-auto px-4">
          <button
            onClick={() => {
              if (backTarget) {
                navigate(backTarget);
                return;
              }
              if (window.history.length > 1) {
                navigate(-1);
                return;
              }
              navigate('/cyclopedia');
            }}
            className="group mb-6 flex items-center gap-2 text-slate-400 transition-colors hover:text-white"
          >
            <ArrowLeft size={18} className="transition-transform group-hover:-translate-x-1" />
            {t('creature.backToCyclopedia')}
          </button>

          <div className="flex flex-col items-start gap-8 md:flex-row">
            <motion.div initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="relative aspect-square w-full overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/80 p-8 shadow-2xl shadow-black/50 md:w-64">
              <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-red-500/5" />
              <ImageWithFallback
                src={`/api/v1/creatures/${creature.id}/image`}
                alt={creature.name}
                className="h-full w-full object-contain drop-shadow-[0_0_15px_rgba(0,0,0,0.6)]"
                containerClassName="h-full w-full"
                fallbackLabel="Creature"
              />
            </motion.div>

            <div className="flex-1 space-y-6">
              <div>
                <motion.h1 initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="mb-2 text-4xl font-serif font-bold tracking-tight text-white md:text-6xl">
                  {creature.name}
                </motion.h1>
                <div className="flex flex-wrap gap-3 text-sm">
                  {creature.is_boss && (
                    <span className="rounded-lg border border-red-500/30 bg-red-500/20 px-3 py-1 font-semibold text-red-300">Boss encounter</span>
                  )}
                  <span className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-1 font-semibold text-amber-300">{creature.difficulty || 'Unknown difficulty'}</span>
                  <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-slate-300">{creature.occurrence || 'Unknown occurrence'}</span>
                  <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-slate-300">Cyclopedia class: {creature.bestiary_class || 'Unknown'}</span>
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
                  { label: 'Cyclopedia level', value: creature.bestiary_level || 'Unknown', icon: Gem, color: 'text-emerald-300' },
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
            <p className="mb-2 text-lg leading-relaxed text-slate-300">{overviewText}</p>
            {overviewNeedsToggle && (
              <button
                onClick={() => setShowFullOverview((value) => !value)}
                className="mb-4 text-sm font-medium text-amber-300 transition hover:text-amber-200"
              >
                {showFullOverview ? 'Show less' : 'Show more'}
              </button>
            )}
            <p className="text-sm leading-relaxed text-slate-400">{creature.behavior || 'Behavior not available.'}</p>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h2 className="flex items-center gap-2 text-xl font-serif font-bold text-amber-500">
                <Gem size={20} /> Loot & Drops
              </h2>
              <div className="text-sm text-slate-500">Source values are shown as-is. Unknown means the source did not expose an exact drop chance.</div>
            </div>
            <LootDisplay items={creature.loot_items} />
          </div>
        </div>

        <div className="space-y-8 lg:col-span-4">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-white">
              <MapPin className="text-amber-500" size={20} /> Known Locations
            </h2>
            <div className="space-y-2 text-sm text-slate-300">
              {(creature.locations?.length ?? 0) > 0 ? creature.locations!.map((location) => (
                <div key={location} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">{location}</div>
              )) : <div className="text-slate-500">Not available</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 text-lg font-bold text-white">{creature.is_boss ? 'Access Requirements (Missions/Quests)' : 'Related Tasks'}</h2>
            <div className="space-y-2 text-sm text-slate-300">
              {displayRequirements.length > 0 ? displayRequirements.map((task) => (
                <div key={task} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">{task}</div>
              )) : <div className="text-slate-500">Not available</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 backdrop-blur">
            <h2 className="mb-4 text-lg font-bold text-white">Sources & Completeness</h2>
            <div className="space-y-2 text-sm text-slate-300">
              <div>Sources: {(creature.data_sources?.length ?? 0) > 0 ? creature.data_sources!.join(', ') : 'Unknown'}</div>
              <div>Missing fields: {(creature.missing_fields?.length ?? 0) > 0 ? creature.missing_fields!.join(', ') : 'None'}</div>
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
