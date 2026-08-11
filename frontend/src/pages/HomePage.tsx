import { useEffect, useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ArrowRight,
  BookOpen,
  Clock3,
  Gem,
  MapPin,
  Shield,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Card, Page, PageHeader, Section } from '../components/ui';
import type { KnowledgeSearchSection } from '../components/search/KnowledgeSearchBox';
import AssistantChat from '../components/assistant/AssistantChat';
import { activityApi, type UserActivityEntry } from '../services/activity';
import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

interface QuestHistoryEntry {
  id: number;
  questId: string;
  title: string;
  createdAt: string;
}

interface HomeSearchOption {
  key: KnowledgeSearchSection;
  icon: LucideIcon;
  title: string;
  help: string;
  to: string;
  artUrl?: string;
}

/*
 * Future Tibia-style illustrations can be assigned here without
 * changing Home layout. Local synchronized media remains the fallback.
 *
 * Example:
 *
 * creatures: '/assets/home/creatures.webp',
 * bosses: '/assets/home/bosses.webp',
 * items: '/assets/home/items.webp',
 * quests: '/assets/home/quests.webp',
 * zones: '/assets/home/zones.webp',
 */
const HOME_CUSTOM_ART: Partial<
  Record<KnowledgeSearchSection, string>
> = {};

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated, user } = useAuth();

  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [capabilityArt, setCapabilityArt] = useState<
    Partial<Record<KnowledgeSearchSection, string>>
  >({});

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

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    void Promise.allSettled([
      creaturesApi.getHighlights(8, controller.signal),
      creaturesApi.getBosses(
        { skip: 0, limit: 8 },
        controller.signal,
      ),
      itemsApi.getHighlights(8, controller.signal),
      huntZonesApi.getHighlights(8, controller.signal),
    ]).then(([creatures, bosses, items, zones]) => {
      if (!mounted) {
        return;
      }

      const next: Partial<
        Record<KnowledgeSearchSection, string>
      > = {};

      if (creatures.status === 'fulfilled') {
        const creature = creatures.value.find(
          (row) => !row.is_boss,
        );

        if (creature) {
          next.creatures = `/api/v1/creatures/${creature.id}/image`;
        }
      }

      if (bosses.status === 'fulfilled') {
        const boss = bosses.value[0];

        if (boss) {
          next.bosses = `/api/v1/creatures/${boss.id}/image`;
        }
      }

      if (items.status === 'fulfilled') {
        const item = items.value.find(
          (row) => row.image_item_id != null || row.id != null,
        );
        const imageId = item?.image_item_id ?? item?.id;

        if (imageId != null) {
          next.items = `/api/v1/items/${imageId}/image`;
        }
      }

      if (zones.status === 'fulfilled') {
        const zone = zones.value[0];

        if (zone) {
          next.zones = `/api/v1/hunt-zones/${zone.id}/map-image`;
        }
      }

      setCapabilityArt(next);
    });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const questHistory = useMemo<QuestHistoryEntry[]>(() => {
    const seen = new Set<string>();
    const entries: QuestHistoryEntry[] = [];

    for (const entry of activity) {
      if (
        entry.activity_type !== 'view_quest' ||
        !entry.entity_id
      ) {
        continue;
      }

      const questId = String(entry.entity_id);

      if (seen.has(questId)) {
        continue;
      }

      seen.add(questId);
      entries.push({
        id: entry.id,
        questId,
        title:
          String(entry.metadata?.name || '').trim() ||
          t('home.questHistory.unknownQuest'),
        createdAt: entry.created_at,
      });

      if (entries.length === 5) {
        break;
      }
    }

    return entries;
  }, [activity, t]);

  const searchOptions: HomeSearchOption[] = [
    {
      key: 'creatures',
      icon: BookOpen,
      title: t(
        'home.assistantPreview.categories.creatures.title',
      ),
      help: t(
        'home.assistantPreview.categories.creatures.help',
      ),
      to: '/cyclopedia?tab=creatures',
      artUrl:
        HOME_CUSTOM_ART.creatures || capabilityArt.creatures,
    },
    {
      key: 'bosses',
      icon: Shield,
      title: t('home.assistantPreview.categories.bosses.title'),
      help: t('home.assistantPreview.categories.bosses.help'),
      to: '/cyclopedia?tab=bosses',
      artUrl: HOME_CUSTOM_ART.bosses || capabilityArt.bosses,
    },
    {
      key: 'items',
      icon: Gem,
      title: t('home.assistantPreview.categories.items.title'),
      help: t('home.assistantPreview.categories.items.help'),
      to: '/cyclopedia?tab=items',
      artUrl: HOME_CUSTOM_ART.items || capabilityArt.items,
    },
    {
      key: 'quests',
      icon: BookOpen,
      title: t('home.assistantPreview.categories.quests.title'),
      help: t('home.assistantPreview.categories.quests.help'),
      to: '/cyclopedia?tab=quests',
      artUrl: HOME_CUSTOM_ART.quests || capabilityArt.quests,
    },
    {
      key: 'zones',
      icon: MapPin,
      title: t('home.assistantPreview.categories.zones.title'),
      help: t('home.assistantPreview.categories.zones.help'),
      to: '/cyclopedia?tab=zones',
      artUrl: HOME_CUSTOM_ART.zones || capabilityArt.zones,
    },
  ];

  const clearActivity = async () => {
    setClearingHistory(true);

    try {
      await activityApi.clearMine();
      setActivity([]);
    } finally {
      setClearingHistory(false);
    }
  };

  const formatDate = (value: string) =>
    new Date(value).toLocaleString(i18n.language, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });

  return (
    <Page className="space-y-7">
      <section className="relative overflow-hidden rounded-3xl border border-line bg-surface-raised p-5 sm:p-8 lg:p-10">
        <div className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 left-1/3 size-80 rounded-full bg-accent/10 blur-3xl" />

        <div className="relative min-w-0">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="size-3.5" />
            {t('home.assistantPreview.status')}
          </div>

          <PageHeader
            className="mb-5"
            eyebrow={t('home.assistantPreview.eyebrow')}
            title={
              isAuthenticated
                ? t(
                    'home.assistantPreview.titleAuthenticated',
                    { username: user?.username || '' },
                  )
                : t('home.assistantPreview.titleGuest')
            }
            subtitle={t('home.assistantPreview.subtitle')}
          />
          <AssistantChat />
        </div>
      </section>

      {isAuthenticated && questHistory.length > 0 ? (
        <Section aria-labelledby="home-quest-history">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2
                id="home-quest-history"
                className="flex items-center gap-2 text-lg font-semibold"
              >
                <Clock3 className="size-5 text-primary" />
                {t('home.questHistory.title')}
              </h2>

              <p className="text-sm text-content-muted">
                {t('home.questHistory.help')}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Link
                to="/cyclopedia?tab=quests&view=history"
                className="app-button-secondary app-button-sm"
              >
                {t('home.questHistory.viewAll')}
              </Link>

              <button
                type="button"
                onClick={() => void clearActivity()}
                disabled={clearingHistory}
                className="app-button-ghost app-button-sm"
              >
                {clearingHistory
                  ? t('home.questHistory.clearing')
                  : t('home.questHistory.clear')}
              </button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {questHistory.map((entry) => (
              <Link
                key={entry.questId}
                to={`/quests/${encodeURIComponent(
                  entry.questId,
                )}`}
                className="min-w-0"
              >
                <Card className="h-full p-4 transition hover:-translate-y-0.5 hover:border-primary/50 motion-reduce:transform-none">
                  <BookOpen className="size-4 text-primary" />
                  <h3 className="mt-3 line-clamp-2 font-semibold">
                    {entry.title}
                  </h3>
                  <p className="mt-1 text-sm text-content-secondary">
                    {t('home.questHistory.open')}
                  </p>
                  <p className="mt-3 text-xs text-content-muted">
                    {formatDate(entry.createdAt)}
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        </Section>
      ) : null}

      <Section aria-labelledby="home-search-options">
        <div>
          <h2
            id="home-search-options"
            className="text-lg font-semibold"
          >
            {t('home.assistantPreview.exploreTitle')}
          </h2>

          <p className="text-sm text-content-muted">
            {t('home.assistantPreview.exploreHelp')}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {searchOptions.map((option) => (
            <HomeCapabilityCard
              key={option.key}
              option={option}
            />
          ))}
        </div>
      </Section>
    </Page>
  );
}

function HomeCapabilityCard({
  option,
}: {
  option: HomeSearchOption;
}) {
  const Icon = option.icon;

  return (
    <Link
      to={option.to}
      title={option.help}
      aria-label={`${option.title}: ${option.help}`}
      className="group block h-full"
    >
      <Card className="relative h-full min-h-44 overflow-hidden p-0 transition duration-300 hover:-translate-y-1 hover:border-primary/60 hover:shadow-lg motion-reduce:transform-none motion-reduce:transition-none">
        {option.artUrl ? (
          <div className="pointer-events-none absolute inset-y-0 right-0 w-2/5 overflow-hidden">
            <img
              src={option.artUrl}
              alt=""
              aria-hidden="true"
              loading="lazy"
              className="h-full w-full object-contain object-right opacity-70 transition duration-300 group-hover:scale-110 group-hover:opacity-100 motion-reduce:transform-none"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-surface-raised via-surface-raised/80 to-transparent" />
          </div>
        ) : null}

        <div className="relative z-10 flex h-full flex-col p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary transition duration-300 group-hover:scale-110 group-hover:bg-primary/20 motion-reduce:transform-none">
            <Icon className="size-5" aria-hidden="true" />
          </div>

          <div
            className={option.artUrl ? 'max-w-[72%]' : undefined}
          >
            <h3 className="mt-3 font-semibold">
              {option.title}
            </h3>

            <p className="mt-1 text-sm text-content-secondary">
              {option.help}
            </p>
          </div>

          <ArrowRight className="mt-auto size-4 translate-y-2 self-end text-primary opacity-0 transition duration-300 group-hover:translate-x-1 group-hover:translate-y-0 group-hover:opacity-100 motion-reduce:transform-none" />
        </div>
      </Card>
    </Link>
  );
}
