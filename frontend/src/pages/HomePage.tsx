import { FormEvent, useEffect, useMemo, useState } from 'react';
import { ArrowRight, BookOpen, Clock3, Gem, Map, MapPin, Search, Shield, TrendingUp, UserCircle2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Alert, Card, EmptyState, LoadingState, Page, PageHeader, Panel, Section } from '../components/ui';
import { activityApi, type UserActivityEntry } from '../services/activity';
import { creaturesApi, huntZonesApi, itemsApi } from '../services/api';
import type { CreatureSimple, HuntZone, ItemSearchResult } from '../types';
import { useAuth } from '../context/AuthContext';

interface RecentCreature { id: number; slug?: string; name: string; image_url?: string; viewed_at: string }

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const [section, setSection] = useState<'creatures' | 'bosses' | 'quests'>('creatures');
  const [query, setQuery] = useState('');
  const [featuredCreatures, setFeaturedCreatures] = useState<CreatureSimple[]>([]);
  const [topItems, setTopItems] = useState<ItemSearchResult[]>([]);
  const [topZones, setTopZones] = useState<HuntZone[]>([]);
  const [highlightsLoading, setHighlightsLoading] = useState(true);
  const [highlightsError, setHighlightsError] = useState(false);
  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;
    void Promise.allSettled([
      creaturesApi.getHighlights(8, controller.signal),
      itemsApi.getHighlights(4, controller.signal),
      huntZonesApi.getHighlights(4, controller.signal),
    ]).then(([creatures, items, zones]) => {
      if (!mounted) return;
      if (creatures.status === 'fulfilled') setFeaturedCreatures(creatures.value);
      if (items.status === 'fulfilled') setTopItems(items.value);
      if (zones.status === 'fulfilled') setTopZones(zones.value);
      setHighlightsError([creatures, items, zones].some(result => result.status === 'rejected'));
      setHighlightsLoading(false);
    });
    return () => { mounted = false; controller.abort(); };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) { setActivity([]); return undefined; }
    const controller = new AbortController();
    setActivityLoading(true);
    setActivityError(false);
    void activityApi.getMine(12, controller.signal)
      .then(setActivity)
      .catch(() => { setActivity([]); setActivityError(true); })
      .finally(() => setActivityLoading(false));
    return () => controller.abort();
  }, [isAuthenticated]);

  const recentCreatures = useMemo<RecentCreature[]>(() => {
    try { return JSON.parse(localStorage.getItem('recentCreatures') || '[]').slice(0, 8); } catch { return []; }
  }, []);
  const continueEntries = useMemo(() => activity.map(entry => {
    if (entry.activity_type === 'view_creature' || entry.activity_type === 'view_boss') {
      const slug = entry.metadata?.slug || entry.entity_id;
      return slug ? { id: entry.id, to: `/creatures/${slug}`, title: entry.metadata?.name || t('home.activity.creatureViewed'), subtitle: t('home.activity.openCreature'), createdAt: entry.created_at } : null;
    }
    if (entry.activity_type === 'view_quest' && entry.entity_id) return { id: entry.id, to: `/quests/${entry.entity_id}`, title: entry.metadata?.name || t('home.activity.questViewed'), subtitle: t('home.activity.openQuest'), createdAt: entry.created_at };
    if (entry.activity_type === 'search') return { id: entry.id, to: `/cyclopedia?tab=${encodeURIComponent(entry.entity_type || 'creatures')}${entry.query ? `&q=${encodeURIComponent(entry.query)}` : ''}`, title: entry.query ? t('home.activity.searchWithQuery', { query: entry.query }) : t('home.activity.searchNoQuery'), subtitle: t('home.activity.repeatSearch'), createdAt: entry.created_at };
    if (entry.activity_type === 'hunt_search') return { id: entry.id, to: '/planner', title: t('home.activity.huntPlan'), subtitle: t('home.activity.openPlanner'), createdAt: entry.created_at };
    return null;
  }).filter((entry): entry is NonNullable<typeof entry> => Boolean(entry)).slice(0, 8), [activity, t]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams({ tab: section });
    if (query.trim()) params.set('q', query.trim());
    navigate(`/cyclopedia?${params.toString()}`);
  };
  const clearActivity = async () => { try { await activityApi.clearMine(); setActivity([]); } catch { setActivityError(true); } };
  const date = (value: string) => new Date(value).toLocaleString(i18n.language);

  return <Page className="space-y-8">
    <section className="relative overflow-hidden rounded-2xl border border-line bg-surface-raised p-5 sm:p-8 lg:p-10">
      <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-primary/10 blur-3xl" />
      <div className="relative max-w-3xl">
        <PageHeader className="mb-5" eyebrow={t('home.eyebrow')} title={isAuthenticated ? t('home.welcomeBack', { username: user?.username || '' }) : t('home.guestTitle')} subtitle={t('home.subtitle')} />
        <form onSubmit={submitSearch} className="grid gap-2 rounded-xl border border-line bg-surface-overlay p-2 sm:grid-cols-[10rem_minmax(0,1fr)_auto]" role="search">
          <select aria-label={t('home.discovery.section')} value={section} onChange={event => setSection(event.target.value as typeof section)} className="ds-select">
            <option value="creatures">{t('nav.creatures')}</option><option value="bosses">{t('nav.bosses')}</option><option value="quests">{t('nav.quests')}</option>
          </select>
          <label className="relative min-w-0"><span className="sr-only">{t('home.discovery.label')}</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><input className="app-input pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('home.discovery.placeholder')} /></label>
          <button className="app-button-primary" type="submit">{t('home.discovery.search')}<ArrowRight className="size-4" /></button>
        </form>
        <p className="mt-2 text-xs text-content-muted">{t('home.discovery.localOnly')}</p>
      </div>
    </section>

    <Section aria-labelledby="home-shortcuts">
      <h2 id="home-shortcuts" className="text-lg font-semibold">{t('home.shortcuts.title')}</h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { to: '/cyclopedia', icon: BookOpen, title: t('home.shortcuts.cyclopedia'), text: t('home.shortcuts.cyclopediaHelp') },
          { to: '/planner', icon: Map, title: t('home.shortcuts.planner'), text: t('home.shortcuts.plannerHelp') },
          { to: '/cyclopedia?tab=quests', icon: Gem, title: t('home.shortcuts.quests'), text: t('home.shortcuts.questsHelp') },
          isAuthenticated ? { to: '/guild/dashboard', icon: Shield, title: t('home.shortcuts.guild'), text: t('home.shortcuts.guildHelp') } : { to: '/login', icon: UserCircle2, title: t('home.shortcuts.account'), text: t('home.shortcuts.accountHelp') },
        ].map(item => { const Icon = item.icon; return <Link key={item.to} to={item.to}><Card className="h-full p-4 transition hover:border-primary/50"><Icon className="size-5 text-primary" /><h3 className="mt-3 font-semibold">{item.title}</h3><p className="mt-1 text-sm text-content-secondary">{item.text}</p></Card></Link>; })}
      </div>
    </Section>

    {isAuthenticated ? <Panel className="p-4 sm:p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">{t('home.profileCard.title')}</h2><p className="text-sm text-content-secondary">{t('home.profileCard.subtitle')}</p></div><Link to="/profile" className="app-button-secondary app-button-sm">{t('home.profileCard.manage')}</Link></div><dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[
      ['character', user?.tibia_character_name], ['world', user?.world_name], ['guild', user?.guild_name], ['vocation', user?.vocation],
    ].map(([key, value]) => <div key={key} className="rounded-lg bg-surface-raised p-3"><dt className="text-xs uppercase tracking-wide text-content-muted">{t(`home.profileCard.${key}`)}</dt><dd className="mt-1 font-semibold">{value || t('home.profileCard.notSet')}</dd></div>)}</dl></Panel> : null}

    <Section aria-labelledby="home-activity">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="home-activity" className="flex items-center gap-2 text-lg font-semibold"><Clock3 className="size-5 text-primary" />{t('home.continueTitle')}</h2><p className="text-sm text-content-muted">{t('home.continueHelp')}</p></div>{isAuthenticated && continueEntries.length ? <button onClick={clearActivity} className="app-button-ghost app-button-sm">{t('home.clearHistory')}</button> : null}</div>
      {activityError ? <Alert tone="warning">{t('home.activityUnavailable')}</Alert> : null}
      {activityLoading ? <LoadingState title={t('home.loadingHistory')} /> : (isAuthenticated ? continueEntries : recentCreatures).length === 0 ? <EmptyState title={isAuthenticated ? t('home.emptyHistory') : t('home.emptyRecentGuest')} description={t('home.emptyActivityHelp')} /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{isAuthenticated ? continueEntries.map(entry => <Link key={entry.id} to={entry.to}><Card className="h-full p-4"><h3 className="font-semibold">{entry.title}</h3><p className="mt-1 text-sm text-content-secondary">{entry.subtitle}</p><p className="mt-3 text-xs text-content-muted">{date(entry.createdAt)}</p></Card></Link>) : recentCreatures.map(entry => <Link key={entry.id} to={`/creatures/${entry.slug || entry.id}`}><Card className="h-full p-4"><h3 className="font-semibold">{entry.name}</h3><p className="mt-3 text-xs text-content-muted">{date(entry.viewed_at)}</p></Card></Link>)}</div>}
    </Section>

    <Section aria-labelledby="home-discovery">
      <div><h2 id="home-discovery" className="flex items-center gap-2 text-lg font-semibold"><TrendingUp className="size-5 text-primary" />{t('home.discoveryData.title')}</h2><p className="text-sm text-content-muted">{t('home.discoveryData.help')}</p></div>
      {highlightsError ? <Alert tone="warning">{t('home.partialHighlights')}</Alert> : null}
      {highlightsLoading ? <LoadingState title={t('home.loadingHighlights')} /> : featuredCreatures.length === 0 && topItems.length === 0 && topZones.length === 0 ? <EmptyState title={t('home.emptyFeatured')} description={t('home.discoveryData.emptyHelp')} /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {featuredCreatures.slice(0, 8).map(creature => <Link key={creature.id} to={`/creatures/${creature.slug || creature.id}`}><Card className="h-full p-4"><BadgeLabel>{t('home.discoveryData.creature')}</BadgeLabel><h3 className="mt-2 font-semibold">{creature.name}</h3><p className="mt-1 text-xs text-content-secondary">{t('home.discoveryData.creatureStats', { hp: creature.hitpoints.toLocaleString(), exp: creature.experience.toLocaleString() })}</p></Card></Link>)}
        {topItems.map(item => <Card key={item.normalized_name} className="p-4"><BadgeLabel>{t('home.discoveryData.item')}</BadgeLabel><h3 className="mt-2 font-semibold">{item.item_name}</h3><p className="mt-1 text-xs text-content-secondary">{t('home.discoveryData.dropSources', { count: item.drops.length })}</p></Card>)}
        {topZones.map(zone => <Card key={zone.id} className="p-4"><BadgeLabel>{t('home.discoveryData.zone')}</BadgeLabel><h3 className="mt-2 flex items-center gap-2 font-semibold"><MapPin className="size-4 text-primary" />{zone.name}</h3><p className="mt-1 text-xs text-content-secondary">{t('home.discoveryData.minimumLevel', { level: zone.min_level ?? t('common.notAvailable') })}</p></Card>)}
      </div>}
    </Section>
  </Page>;
}

function BadgeLabel({ children }: { children: React.ReactNode }) { return <span className="text-xs font-semibold uppercase tracking-wide text-primary">{children}</span>; }
