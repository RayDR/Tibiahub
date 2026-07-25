import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock3, Gem, MapPin, TrendingUp, UserCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { creaturesApi, huntZonesApi, itemsApi } from '../services/api';
import type { CreatureSimple, HuntZone, ItemSearchResult } from '../types';
import { useAuth } from '../context/AuthContext';
import { activityApi, type UserActivityEntry } from '../services/activity';

interface RecentCreature {
  id: number;
  slug?: string;
  name: string;
  image_url?: string;
  viewed_at: string;
}

const HomePage: React.FC = () => {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [cyclopediaSection, setCyclopediaSection] = useState<'creatures' | 'bosses' | 'quests'>('creatures');
  const [featuredCreatures, setFeaturedCreatures] = useState<CreatureSimple[]>([]);
  const [topItems, setTopItems] = useState<ItemSearchResult[]>([]);
  const [topZones, setTopZones] = useState<HuntZone[]>([]);
  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    const loadHighlights = async () => {
      const [creaturesResult, itemsResult, zonesResult] = await Promise.allSettled([
        creaturesApi.getHighlights(12, controller.signal),
        itemsApi.getHighlights(8, controller.signal),
        huntZonesApi.getHighlights(6, controller.signal),
      ]);

      if (!mounted) {
        return;
      }

      if (creaturesResult.status === 'fulfilled') {
        setFeaturedCreatures(creaturesResult.value);
      } else {
        setFeaturedCreatures([]);
        console.warn('Home creatures highlights unavailable');
      }

      if (itemsResult.status === 'fulfilled') {
        setTopItems(itemsResult.value);
      } else {
        setTopItems([]);
        console.warn('Home items highlights unavailable');
      }

      if (zonesResult.status === 'fulfilled') {
        setTopZones(zonesResult.value);
      } else {
        setTopZones([]);
        console.warn('Home hunt zones highlights unavailable');
      }
    };

    void loadHighlights();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setActivity([]);
      return;
    }

    const controller = new AbortController();
    let mounted = true;

    const loadActivity = async () => {
      try {
        if (mounted) {
          setActivityLoading(true);
        }
        const result = await activityApi.getMine(12, controller.signal);
        if (mounted) {
          setActivity(result);
        }
      } catch {
        if (mounted) {
          setActivity([]);
        }
      } finally {
        if (mounted) {
          setActivityLoading(false);
        }
      }
    };

    void loadActivity();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [isAuthenticated]);

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

  const continueEntries = useMemo(() => {
    return activity
      .map((entry) => {
        if (entry.activity_type === 'view_creature' || entry.activity_type === 'view_boss') {
          const slug = entry.metadata?.slug || entry.entity_id;
          if (!slug) return null;
          return {
            id: `activity-${entry.id}`,
            to: `/creatures/${slug}`,
            title: entry.metadata?.name || t('home.activity.creatureViewed'),
            subtitle: t('home.activity.openCreature'),
            createdAt: entry.created_at,
          };
        }
        if (entry.activity_type === 'view_quest' && entry.entity_id) {
          return {
            id: `activity-${entry.id}`,
            to: `/quests/${entry.entity_id}`,
            title: entry.metadata?.name || t('home.activity.questViewed'),
            subtitle: t('home.activity.openQuest'),
            createdAt: entry.created_at,
          };
        }
        if (entry.activity_type === 'search') {
          const tab = entry.entity_type || 'creatures';
          return {
            id: `activity-${entry.id}`,
            to: `/cyclopedia?tab=${encodeURIComponent(tab)}`,
            title: entry.query ? `${t('home.activity.search')}: ${entry.query}` : t('home.activity.searchNoQuery'),
            subtitle: t('home.activity.repeatSearch'),
            createdAt: entry.created_at,
          };
        }
        if (entry.activity_type === 'hunt_search') {
          return {
            id: `activity-${entry.id}`,
            to: '/planner',
            title: t('home.activity.huntPlan'),
            subtitle: t('home.activity.openPlanner'),
            createdAt: entry.created_at,
          };
        }
        return null;
      })
      .filter((entry): entry is { id: string; to: string; title: string; subtitle: string; createdAt: string } => !!entry)
      .slice(0, 8);
  }, [activity, t]);

  const onClearActivity = async () => {
    try {
      await activityApi.clearMine();
      setActivity([]);
    } catch {
      // Keep the page usable even if clear fails.
    }
  };

  return (
    <div className="min-h-screen pb-16 pt-10">
      <section className="mb-10 rounded-2xl border border-line bg-surface-base/70 p-6">
        <h1 className="text-3xl font-bold text-primary md:text-4xl">
          {isAuthenticated ? t('home.welcomeBack', { username: user?.username || '' }) : t('home.guestTitle')}
        </h1>
        <p className="mt-3 max-w-3xl text-content-secondary">Explora la Cyclopedia, planea tu proxima hunt y completa tus weekly tasks.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <select
            value={cyclopediaSection}
            onChange={(event) => setCyclopediaSection(event.target.value as 'creatures' | 'bosses' | 'quests')}
            className="rounded-lg border border-line bg-surface-base px-4 py-2 text-sm text-content-primary"
          >
            <option value="creatures">{t('nav.creatures')}</option>
            <option value="bosses">{t('nav.bosses')}</option>
            <option value="quests">{t('nav.quests')}</option>
          </select>
          <Link to={`/cyclopedia?tab=${cyclopediaSection === 'quests' ? 'quests' : cyclopediaSection}`} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-content-inverse hover:bg-primary-hover">
            {t('home.openCyclopedia')}
          </Link>
          <Link to="/planner" className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-content-primary hover:border-primary/40">
            {t('home.openPlanner')}
          </Link>
          {isAuthenticated && (
            <Link to="/guild/dashboard" className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-content-primary hover:border-primary/40">
              Open Guild
            </Link>
          )}
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Link to="/cyclopedia?tab=creatures" className="rounded-xl border border-line bg-surface-base/50 p-4 text-sm text-content-primary hover:border-primary/40">
            <div className="font-semibold text-primary">Cyclopedia</div>
            <div className="mt-1 text-xs text-content-secondary">Creatures, bosses, loot, quests y zones.</div>
          </Link>
          <Link to="/planner" className="rounded-xl border border-line bg-surface-base/50 p-4 text-sm text-content-primary hover:border-primary/40">
            <div className="font-semibold text-primary">Hunt Planner</div>
            <div className="mt-1 text-xs text-content-secondary">Recomendaciones por vocacion, nivel y objetivo.</div>
          </Link>
          <Link to="/cyclopedia?tab=quests" className="rounded-xl border border-line bg-surface-base/50 p-4 text-sm text-content-primary hover:border-primary/40">
            <div className="font-semibold text-primary">Quests</div>
            <div className="mt-1 text-xs text-content-secondary">Busca quests reales y revisa requisitos.</div>
          </Link>
          {isAuthenticated ? (
            <Link to="/guild/dashboard" className="rounded-xl border border-line bg-surface-base/50 p-4 text-sm text-content-primary hover:border-primary/40">
              <div className="font-semibold text-primary">Guild</div>
              <div className="mt-1 text-xs text-content-secondary">Gestion, eventos y actividad de equipo.</div>
            </Link>
          ) : (
            <Link to="/login" className="rounded-xl border border-line bg-surface-base/50 p-4 text-sm text-content-primary hover:border-primary/40">
              <div className="font-semibold text-primary">Inicia sesion</div>
              <div className="mt-1 text-xs text-content-secondary">Activa historial y atajos personalizados.</div>
            </Link>
          )}
        </div>
      </section>

      {isAuthenticated && (
        <section className="mb-10 rounded-2xl border border-line bg-surface-base/60 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <UserCircle2 className="text-primary" size={24} />
              <div>
                <h2 className="text-xl font-semibold text-content-primary">{t('home.profileCard.title')}</h2>
                <p className="text-sm text-content-secondary">{t('home.profileCard.subtitle')}</p>
              </div>
            </div>
            <Link to="/profile" className="rounded-lg border border-line px-3 py-2 text-sm text-content-primary hover:border-primary/40">
              {t('home.profileCard.manage')}
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-line bg-surface-base/50 p-3 text-sm text-content-secondary">
              <div className="text-xs uppercase tracking-wide text-content-muted">{t('home.profileCard.character')}</div>
              <div className="mt-1 font-semibold text-content-primary">{user?.tibia_character_name || t('home.profileCard.notSet')}</div>
            </div>
            <div className="rounded-xl border border-line bg-surface-base/50 p-3 text-sm text-content-secondary">
              <div className="text-xs uppercase tracking-wide text-content-muted">{t('home.profileCard.world')}</div>
              <div className="mt-1 font-semibold text-content-primary">{user?.world_name || t('home.profileCard.notSet')}</div>
            </div>
            <div className="rounded-xl border border-line bg-surface-base/50 p-3 text-sm text-content-secondary">
              <div className="text-xs uppercase tracking-wide text-content-muted">{t('home.profileCard.guild')}</div>
              <div className="mt-1 font-semibold text-content-primary">{user?.guild_name || t('home.profileCard.notSet')}</div>
            </div>
            <div className="rounded-xl border border-line bg-surface-base/50 p-3 text-sm text-content-secondary">
              <div className="text-xs uppercase tracking-wide text-content-muted">{t('home.profileCard.vocation')}</div>
              <div className="mt-1 font-semibold text-content-primary">{user?.vocation || t('home.profileCard.notSet')}</div>
            </div>
          </div>
        </section>
      )}

      <section className="mb-10">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-primary">
            <Clock3 size={18} />
            <h2 className="text-xl font-semibold">{t('home.continueTitle')}</h2>
          </div>
          {isAuthenticated && continueEntries.length > 0 && (
            <button onClick={onClearActivity} className="rounded-lg border border-line px-3 py-1.5 text-xs text-content-secondary hover:border-danger/40 hover:text-danger">
              {t('home.clearHistory')}
            </button>
          )}
        </div>
        {activityLoading ? (
          <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-sm text-content-secondary">{t('home.loadingHistory')}</div>
        ) : isAuthenticated ? (
          continueEntries.length === 0 ? (
            <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-sm text-content-secondary">{t('home.emptyHistory')}</div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {continueEntries.map((entry) => (
                <Link key={entry.id} to={entry.to} className="rounded-xl border border-line bg-surface-base/60 p-4 transition hover:border-primary/40">
                  <div className="text-sm font-semibold text-content-primary">{entry.title}</div>
                  <div className="mt-1 text-xs text-content-secondary">{entry.subtitle}</div>
                  <div className="mt-2 text-xs text-content-muted">{new Date(entry.createdAt).toLocaleString()}</div>
                </Link>
              ))}
            </div>
          )
        ) : recentCreatures.length === 0 ? (
          <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-sm text-content-secondary">{t('home.emptyRecentGuest')}</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {recentCreatures.map((creature) => (
              <Link key={`recent-${creature.id}`} to={`/creatures/${creature.slug || creature.id}`} className="rounded-xl border border-line bg-surface-base/60 p-4 transition hover:border-primary/40">
                <div className="text-sm font-semibold text-content-primary">{creature.name}</div>
                <div className="mt-1 text-xs text-content-muted">{new Date(creature.viewed_at).toLocaleString()}</div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="mb-10">
        <div className="mb-4 flex items-center gap-2 text-primary">
          <TrendingUp size={18} />
          <h2 className="text-xl font-semibold">{t('home.featured')}</h2>
        </div>
        {featuredCreatures.length === 0 ? (
          <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-sm text-content-secondary">{t('home.emptyFeatured')}</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {featuredCreatures.map((creature) => (
              <Link
                key={creature.id}
                to={`/creatures/${creature.slug || creature.id}`}
                className="rounded-xl border border-line bg-surface-base/60 p-4 transition hover:border-primary/40"
              >
                <div className="mb-2 text-lg font-semibold text-content-primary">{creature.name}</div>
                <div className="text-xs text-content-secondary">HP {creature.hitpoints.toLocaleString()} · EXP {creature.experience.toLocaleString()}</div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="mb-10">
        <div className="mb-4 flex items-center gap-2 text-primary">
          <Gem size={18} />
          <h2 className="text-xl font-semibold">{t('home.topSearched')}</h2>
        </div>
        {topItems.length === 0 && topZones.length === 0 ? (
          <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-sm text-content-secondary">{t('home.emptyTop')}</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {topItems.map((item) => (
              <div key={item.normalized_name} className="rounded-xl border border-line bg-surface-base/60 p-4">
                <div className="text-sm font-semibold text-content-primary">{item.item_name}</div>
                <div className="mt-1 text-xs text-content-secondary">{item.drops.length} {t('home.creatureCount')}</div>
              </div>
            ))}
            {topZones.map((zone) => (
              <div key={`zone-${zone.id}`} className="rounded-xl border border-line bg-surface-base/60 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-content-primary">
                  <MapPin size={14} /> {zone.name}
                </div>
                <div className="mt-1 text-xs text-content-secondary">{t('home.minLevel')}: {zone.min_level ?? 'N/A'}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default HomePage;
