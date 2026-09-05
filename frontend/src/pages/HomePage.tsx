import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Clock3,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Card, Page, Section } from '../components/ui';
import type { KnowledgeSearchSection } from '../components/search/KnowledgeSearchBox';
import AssistantChat from '../components/assistant/AssistantChat';
import { activityApi, type UserActivityEntry } from '../services/activity';
import { useAuth } from '../context/AuthContext';
import { assistantHeroSessionSeed, selectAssistantHeroCopy } from '../utils/assistantHeroCopy';
import KnowledgeCategoryIcon from '../components/knowledge/KnowledgeCategoryIcon';

interface QuestHistoryEntry {
  id: number;
  questId: string;
  title: string;
  createdAt: string;
}

interface HomeSearchOption {
  key: KnowledgeSearchSection;
  title: string;
  help: string;
  to: string;
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();
  const heroCopySeed = useMemo(() => assistantHeroSessionSeed(), []);
  const assistantCopy = useMemo(
    () => selectAssistantHeroCopy(i18n.resolvedLanguage || i18n.language, new Date(), heroCopySeed),
    [heroCopySeed, i18n.language, i18n.resolvedLanguage],
  );

  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const [clearingHistory, setClearingHistory] = useState(false);

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
      title: t(
        'home.assistantPreview.categories.creatures.title',
      ),
      help: t(
        'home.assistantPreview.categories.creatures.help',
      ),
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
      <section className="assistant-hero relative overflow-hidden">
        <div className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 left-1/3 size-80 rounded-full bg-accent/10 blur-3xl" />

        <div className="relative min-w-0">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary sm:mb-4">
            <Sparkles className="size-3.5" />
            {t('home.assistantPreview.identity')}
          </div>

          <header className="mb-4 max-w-4xl sm:mb-6">
            <h1 className="text-balance font-heading text-[clamp(1.65rem,7vw,2.8rem)] font-bold leading-[1.12] tracking-[0.015em] text-content-primary">
              {assistantCopy.headline}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-content-secondary sm:mt-3 sm:text-base">
              {assistantCopy.supporting}
            </p>
          </header>
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

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
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
  return (
    <Link
      to={option.to}
      title={option.help}
      aria-label={`${option.title}: ${option.help}`}
      className="group block h-full"
    >
      <Card className="relative h-full min-h-44 overflow-hidden p-0 transition duration-300 hover:-translate-y-1 hover:border-primary/60 hover:shadow-lg motion-reduce:transform-none motion-reduce:transition-none">
        <KnowledgeCategoryIcon category={option.key} label={option.title} className="absolute -right-3 -top-2 size-28 rounded-3xl bg-primary/[0.07] opacity-90 transition duration-300 group-hover:scale-110 group-hover:opacity-100 motion-reduce:transform-none" mediaClassName="size-24 p-1" />
        <div className="relative z-10 flex h-full max-w-[72%] flex-col p-4">

          <div>
            <h3 className="mt-1 font-semibold">
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
