import { type CSSProperties, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Clock3,
  Compass,
  Flame,
  History,
  Map,
  Search,
  Sword,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Page } from '../components/ui';
import type { KnowledgeSearchSection } from '../components/search/KnowledgeSearchBox';
import AssistantChat from '../components/assistant/AssistantChat';
import { activityApi, type UserActivityEntry } from '../services/activity';
import { useAuth } from '../context/AuthContext';
import { assistantHeroSessionSeed, selectAssistantHeroCopy } from '../utils/assistantHeroCopy';
import KnowledgeCategoryIcon from '../components/knowledge/KnowledgeCategoryIcon';
import { tibiaApi } from '../services/api';
import type { BoostedCreatureProjection, TibiaBoostedResponse } from '../types';
import { TIBIAHUB_WORLD_BACKGROUND } from '../assets/brand/brandBackground';

interface HomeSearchOption {
  key: KnowledgeSearchSection;
  title: string;
  help: string;
  to: string;
}

interface HomeRecentEntry {
  key: string;
  title: string;
  subtitle: string;
  to: string;
  category: KnowledgeSearchSection;
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();
  const heroCopySeed = useMemo(() => assistantHeroSessionSeed(), []);
  const assistantCopy = useMemo(
    () => selectAssistantHeroCopy(i18n.resolvedLanguage || i18n.language, new Date(), heroCopySeed),
    [heroCopySeed, i18n.language, i18n.resolvedLanguage],
  );
  const isSpanish = (i18n.resolvedLanguage || i18n.language).startsWith('es');

  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [boosted, setBoosted] = useState<TibiaBoostedResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void tibiaApi
      .getBoosted(controller.signal)
      .then(setBoosted)
      .catch(() => {
        // Current-data enrichment is optional; generic Home cards stay intact.
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setActivity([]);
      return undefined;
    }

    const controller = new AbortController();
    void activityApi
      .getMine(50, controller.signal)
      .then(setActivity)
      .catch(() => setActivity([]));

    return () => controller.abort();
  }, [isAuthenticated]);

  const searchOptions: HomeSearchOption[] = [
    {
      key: 'creatures',
      title: t('home.assistantPreview.categories.creatures.title'),
      help: t('home.assistantPreview.categories.creatures.help'),
      to: '/cyclopedia?tab=creatures',
    },
    {
      key: 'bosses',
      title: t('home.assistantPreview.categories.bosses.title'),
      help: t('home.assistantPreview.categories.bosses.help'),
      to: '/cyclopedia?tab=bosses',
    },
    {
      key: 'items',
      title: t('home.assistantPreview.categories.items.title'),
      help: t('home.assistantPreview.categories.items.help'),
      to: '/cyclopedia?tab=loot',
    },
    {
      key: 'quests',
      title: t('home.assistantPreview.categories.quests.title'),
      help: t('home.assistantPreview.categories.quests.help'),
      to: '/cyclopedia?tab=quests',
    },
    {
      key: 'zones',
      title: t('home.assistantPreview.categories.zones.title'),
      help: t('home.assistantPreview.categories.zones.help'),
      to: '/cyclopedia?tab=zones',
    },
    {
      key: 'npcs',
      title: t('home.assistantPreview.categories.npcs.title'),
      help: t('home.assistantPreview.categories.npcs.help'),
      to: '/cyclopedia?tab=npcs',
    },
  ];

  const recentActivity = useMemo<HomeRecentEntry[]>(() => {
    const seen = new Set<string>();
    const entries: HomeRecentEntry[] = [];

    for (const entry of activity) {
      const mapped = mapActivity(entry, searchOptions, isSpanish);
      if (!mapped || seen.has(mapped.key)) continue;
      seen.add(mapped.key);
      entries.push(mapped);
      if (entries.length === 5) break;
    }

    return entries;
  }, [activity, isSpanish, searchOptions]);

  const featuredOptions = useMemo(
    () => [
      searchOptions[0],
      searchOptions[1],
      searchOptions[2],
      searchOptions[3],
      searchOptions[4],
    ],
    [searchOptions],
  );

  const clearActivity = async () => {
    setClearingHistory(true);
    try {
      await activityApi.clearMine();
      setActivity([]);
    } finally {
      setClearingHistory(false);
    }
  };

  const heroStyle = {
    '--home-hero-image': `url("${TIBIAHUB_WORLD_BACKGROUND}")`,
  } as CSSProperties;

  const visualCopy = isSpanish
    ? {
        recent: 'Búsquedas recientes',
        clear: 'Limpiar todo',
        clearing: 'Limpiando…',
        featured: 'Destacado ahora',
        plannerTitle: 'Planea tu próxima cacería',
        plannerHelp: 'Encuentra zonas de caza para tu nivel, vocación y objetivos.',
        plannerAction: 'Abrir Hunt Planner',
        mapTitle: 'Explora el mundo',
        mapHelp: 'Recorre el mapa interactivo y descubre ubicaciones, NPCs y zonas de caza.',
        mapAction: 'Abrir mapa mundial',
        quote: 'El conocimiento es la clave de la aventura.',
      }
    : {
        recent: 'Recent Searches',
        clear: 'Clear all',
        clearing: 'Clearing…',
        featured: 'Popular Right Now',
        plannerTitle: 'Plan Your Next Hunt',
        plannerHelp: 'Find hunt zones for your level, vocation and goals.',
        plannerAction: 'Open Hunt Planner',
        mapTitle: 'Explore the World',
        mapHelp: 'Browse the interactive map and discover locations, NPCs and hunt zones.',
        mapAction: 'Open World Map',
        quote: 'Knowledge is the key to adventure.',
      };

  return (
    <Page className="home-page">
      <section className="home-hero" style={heroStyle} aria-labelledby="home-hero-title">
        <div className="home-hero-copy">
          <h1 id="home-hero-title" className="home-hero-title">
            {highlightTibia(assistantCopy.headline)}
          </h1>
          <p className="home-hero-subtitle">{assistantCopy.supporting}</p>

          <div className="home-hero-assistant">
            <AssistantChat />
          </div>
        </div>

        <div className="home-hero-art" aria-hidden="true">
          <div className="home-hero-quote">
            <span className="home-hero-quote-mark">“</span>
            <p>{visualCopy.quote}</p>
            <small>— TibiaHub</small>
          </div>
        </div>
      </section>

      <section className="home-section" aria-labelledby="home-explore-title">
        <div className="home-section-heading">
          <div>
            <h2 id="home-explore-title">
              <Search className="size-5 text-primary" aria-hidden="true" />
              {t('home.assistantPreview.exploreTitle')}
            </h2>
            <p>{t('home.assistantPreview.exploreHelp')}</p>
          </div>
        </div>

        <div className="home-category-grid">
          {searchOptions.map((option) => (
            <HomeCategoryCard
              key={option.key}
              option={option}
              boosted={
                option.key === 'creatures'
                  ? boosted?.creature
                  : option.key === 'bosses'
                    ? boosted?.boss
                    : undefined
              }
            />
          ))}
        </div>
      </section>

      {recentActivity.length ? (
        <section className="home-section" aria-labelledby="home-recent-title">
          <div className="home-section-heading">
            <h2 id="home-recent-title">
              <History className="size-5 text-primary" aria-hidden="true" />
              {visualCopy.recent}
            </h2>
            <button
              type="button"
              onClick={() => void clearActivity()}
              disabled={clearingHistory}
              className="app-button-ghost app-button-sm"
            >
              {clearingHistory ? visualCopy.clearing : visualCopy.clear}
            </button>
          </div>

          <div className="home-rail">
            {recentActivity.map((entry) => (
              <Link key={entry.key} to={entry.to} className="home-rail-card">
                <span className="home-rail-icon" aria-hidden="true">
                  <KnowledgeCategoryIcon
                    category={entry.category}
                    label={entry.subtitle}
                    className="size-8"
                    mediaClassName="size-7"
                  />
                </span>
                <span className="min-w-0">
                  <strong>{entry.title}</strong>
                  <small>{entry.subtitle}</small>
                </span>
                <ArrowRight className="size-4 text-content-muted" aria-hidden="true" />
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section className="home-section" aria-labelledby="home-featured-title">
        <div className="home-section-heading">
          <h2 id="home-featured-title">
            <Flame className="size-5 text-primary" aria-hidden="true" />
            {visualCopy.featured}
          </h2>
        </div>

        <div className="home-feature-grid">
          {featuredOptions.map((option) => (
            <HomeFeatureCard
              key={option.key}
              option={option}
              boosted={
                option.key === 'creatures'
                  ? boosted?.creature
                  : option.key === 'bosses'
                    ? boosted?.boss
                    : undefined
              }
            />
          ))}
        </div>
      </section>

      <section className="home-cta-grid" aria-label="TibiaHub tools">
        <Link to="/planner" className="home-cta" data-kind="planner">
          <div className="home-cta-copy">
            <div className="home-cta-title">
              <Sword className="size-8 text-primary" aria-hidden="true" />
              <span>{visualCopy.plannerTitle}</span>
            </div>
            <p>{visualCopy.plannerHelp}</p>
            <span className="app-button-primary app-button-sm">
              {visualCopy.plannerAction}
              <ArrowRight className="size-4" aria-hidden="true" />
            </span>
          </div>
          <KnowledgeCategoryIcon
            category="zones"
            label={visualCopy.plannerTitle}
            className="pointer-events-none absolute -right-6 -bottom-8 size-52 opacity-25"
            mediaClassName="size-48"
          />
        </Link>

        <Link to="/map" className="home-cta" data-kind="map">
          <div className="home-cta-copy">
            <div className="home-cta-title">
              <Compass className="size-8 text-primary" aria-hidden="true" />
              <span>{visualCopy.mapTitle}</span>
            </div>
            <p>{visualCopy.mapHelp}</p>
            <span className="app-button-primary app-button-sm">
              {visualCopy.mapAction}
              <ArrowRight className="size-4" aria-hidden="true" />
            </span>
          </div>
          <Map className="pointer-events-none absolute -right-2 -bottom-10 size-48 text-accent opacity-15" aria-hidden="true" />
        </Link>
      </section>
    </Page>
  );
}

function HomeCategoryCard({
  option,
  boosted,
}: {
  option: HomeSearchOption;
  boosted?: BoostedCreatureProjection;
}) {
  const { t } = useTranslation();
  const [imageFailed, setImageFailed] = useState(false);
  const current = boosted?.resolution_state === 'unavailable' ? undefined : boosted;
  const currentName = current?.resolution_state === 'resolved'
    ? current.name
    : current?.source_name;
  const imageUrl = current?.resolution_state === 'resolved'
    && current.media.status === 'available'
    && !imageFailed
    ? current.media.url
    : null;

  useEffect(() => setImageFailed(false), [current?.media.url]);

  return (
    <Link
      to={option.to}
      title={option.help}
      className="home-category-card"
      data-boosted={current ? 'true' : 'false'}
      aria-label={`${option.title}: ${currentName ? t('home.boosted.today', { name: currentName }) : option.help}`}
    >
      {current ? (
        <span className="home-boosted-chip">
          <Flame className="size-3" aria-hidden="true" />
          {t('home.boosted.badge')}
        </span>
      ) : null}

      <span className="home-category-media" aria-hidden="true">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <KnowledgeCategoryIcon
            category={option.key}
            label={option.title}
            className="size-20"
            mediaClassName="size-16"
          />
        )}
      </span>

      <h3>{option.title}</h3>
      <p>{currentName ? t('home.boosted.today', { name: currentName }) : option.help}</p>
      <ArrowRight className="home-category-arrow size-4" aria-hidden="true" />
    </Link>
  );
}

function HomeFeatureCard({
  option,
  boosted,
}: {
  option: HomeSearchOption;
  boosted?: BoostedCreatureProjection;
}) {
  const { t } = useTranslation();
  const [imageFailed, setImageFailed] = useState(false);
  const current = boosted?.resolution_state === 'unavailable' ? undefined : boosted;
  const currentName = current?.resolution_state === 'resolved'
    ? current.name
    : current?.source_name;
  const imageUrl = current?.resolution_state === 'resolved'
    && current.media.status === 'available'
    && !imageFailed
    ? current.media.url
    : null;

  useEffect(() => setImageFailed(false), [current?.media.url]);

  return (
    <Link to={option.to} className="home-feature-card">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setImageFailed(true)}
          className="size-16 object-contain [image-rendering:pixelated]"
        />
      ) : (
        <KnowledgeCategoryIcon
          category={option.key}
          label={option.title}
          className="size-16"
          mediaClassName="size-14"
        />
      )}
      <span className="min-w-0 max-w-full">
        <strong>{currentName || option.title}</strong>
        <small>{currentName ? t('home.boosted.badge') : option.help}</small>
      </span>
    </Link>
  );
}

function mapActivity(
  entry: UserActivityEntry,
  options: HomeSearchOption[],
  isSpanish: boolean,
): HomeRecentEntry | null {
  const type = entry.activity_type;
  const id = entry.entity_id ? String(entry.entity_id) : '';
  const title = String(entry.metadata?.name || entry.query || '').trim();
  if (!title) return null;

  const byKey = (key: KnowledgeSearchSection) => options.find((option) => option.key === key);
  const genericSubtitle = (key: KnowledgeSearchSection) => byKey(key)?.title || key;

  if (type === 'view_creature' && id) {
    return { key: `${type}:${id}`, title, subtitle: genericSubtitle('creatures'), to: `/creatures/${encodeURIComponent(id)}`, category: 'creatures' };
  }
  if (type === 'view_boss' && id) {
    return { key: `${type}:${id}`, title, subtitle: genericSubtitle('bosses'), to: `/creatures/${encodeURIComponent(id)}`, category: 'bosses' };
  }
  if (type === 'view_item' && id) {
    return { key: `${type}:${id}`, title, subtitle: genericSubtitle('items'), to: `/items/${encodeURIComponent(id)}`, category: 'items' };
  }
  if (type === 'view_quest' && id) {
    return { key: `${type}:${id}`, title, subtitle: genericSubtitle('quests'), to: `/quests/${encodeURIComponent(id)}`, category: 'quests' };
  }
  if (type === 'view_zone' && id) {
    return { key: `${type}:${id}`, title, subtitle: genericSubtitle('zones'), to: `/hunt-zones/${encodeURIComponent(id)}`, category: 'zones' };
  }
  if (type === 'hunt_search') {
    return {
      key: `${type}:${entry.query || entry.id}`,
      title,
      subtitle: isSpanish ? 'Búsqueda de cacería' : 'Hunt search',
      to: '/planner',
      category: 'zones',
    };
  }

  return null;
}

function highlightTibia(value: string) {
  const parts = value.split(/(Tibia)/gi);
  return parts.map((part, index) => part.toLowerCase() === 'tibia'
    ? <span key={`${part}-${index}`} className="home-hero-title-emphasis">{part}</span>
    : part);
}
