import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Clock3,
  Gem,
  MapPin,
  Search,
  Shield,
  Sparkles,
  Swords,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Card, Page, PageHeader, Section } from '../components/ui';
import { activityApi, type UserActivityEntry } from '../services/activity';
import { useAuth } from '../context/AuthContext';

type SearchSection = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones';

interface QuestHistoryEntry {
  id: number;
  questId: string;
  title: string;
  createdAt: string;
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const [section, setSection] = useState<SearchSection>('creatures');
  const [query, setQuery] = useState('');
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
      if (entry.activity_type !== 'view_quest' || !entry.entity_id) {
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

  const searchOptions = [
    {
      key: 'creatures' as const,
      icon: BookOpen,
      title: t('home.assistantPreview.categories.creatures.title'),
      help: t('home.assistantPreview.categories.creatures.help'),
      to: '/cyclopedia?tab=creatures',
    },
    {
      key: 'bosses' as const,
      icon: Shield,
      title: t('home.assistantPreview.categories.bosses.title'),
      help: t('home.assistantPreview.categories.bosses.help'),
      to: '/cyclopedia?tab=bosses',
    },
    {
      key: 'items' as const,
      icon: Gem,
      title: t('home.assistantPreview.categories.items.title'),
      help: t('home.assistantPreview.categories.items.help'),
      to: '/cyclopedia?tab=items',
    },
    {
      key: 'quests' as const,
      icon: BookOpen,
      title: t('home.assistantPreview.categories.quests.title'),
      help: t('home.assistantPreview.categories.quests.help'),
      to: '/cyclopedia?tab=quests',
    },
    {
      key: 'zones' as const,
      icon: MapPin,
      title: t('home.assistantPreview.categories.zones.title'),
      help: t('home.assistantPreview.categories.zones.help'),
      to: '/cyclopedia?tab=zones',
    },
  ];

  const starterSearches = [
    {
      key: 'hunt',
      section: 'creatures' as const,
      query: t('home.assistantPreview.prompts.huntQuery'),
      label: t('home.assistantPreview.prompts.hunt'),
    },
    {
      key: 'item',
      section: 'items' as const,
      query: t('home.assistantPreview.prompts.itemQuery'),
      label: t('home.assistantPreview.prompts.item'),
    },
    {
      key: 'quest',
      section: 'quests' as const,
      query: t('home.assistantPreview.prompts.questQuery'),
      label: t('home.assistantPreview.prompts.quest'),
    },
  ];

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();

    const params = new URLSearchParams({ tab: section });

    if (query.trim()) {
      params.set('q', query.trim());
    }

    navigate(`/cyclopedia?${params.toString()}`);
  };

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

        <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,.65fr)] lg:items-start">
          <div className="min-w-0">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="size-3.5" />
              {t('home.assistantPreview.status')}
            </div>

            <PageHeader
              className="mb-5"
              eyebrow={t('home.assistantPreview.eyebrow')}
              title={
                isAuthenticated
                  ? t('home.assistantPreview.titleAuthenticated', {
                      username: user?.username || '',
                    })
                  : t('home.assistantPreview.titleGuest')
              }
              subtitle={t('home.assistantPreview.subtitle')}
            />

            <form
              onSubmit={submitSearch}
              className="grid gap-2 rounded-2xl border border-line bg-surface-overlay p-2 sm:grid-cols-[10rem_minmax(0,1fr)_auto]"
              role="search"
            >
              <select
                aria-label={t('home.assistantPreview.section')}
                value={section}
                onChange={(event) =>
                  setSection(event.target.value as SearchSection)
                }
                className="ds-select"
              >
                <option value="creatures">
                  {t('home.assistantPreview.categories.creatures.title')}
                </option>
                <option value="bosses">
                  {t('home.assistantPreview.categories.bosses.title')}
                </option>
                <option value="items">
                  {t('home.assistantPreview.categories.items.title')}
                </option>
                <option value="quests">
                  {t('home.assistantPreview.categories.quests.title')}
                </option>
                <option value="zones">
                  {t('home.assistantPreview.categories.zones.title')}
                </option>
              </select>

              <label className="relative min-w-0">
                <span className="sr-only">
                  {t('home.assistantPreview.searchLabel')}
                </span>
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
                <input
                  className="app-input pl-9"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t('home.assistantPreview.placeholder')}
                />
              </label>

              <button className="app-button-primary" type="submit">
                {t('home.assistantPreview.search')}
                <ArrowRight className="size-4" />
              </button>
            </form>

            <p className="mt-2 text-xs text-content-muted">
              {t('home.assistantPreview.localOnly')}
            </p>

            <div
              className="mt-4 flex flex-wrap gap-2"
              aria-label={t('home.assistantPreview.quickFilters')}
            >
              {searchOptions.map((option) => {
                const Icon = option.icon;
                const active = section === option.key;

                return (
                  <button
                    key={option.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSection(option.key)}
                    className={
                      active
                        ? 'app-button-secondary app-button-sm border-primary/50 bg-primary/10 text-primary'
                        : 'app-button-ghost app-button-sm'
                    }
                  >
                    <Icon className="size-3.5" />
                    {option.title}
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="rounded-2xl border border-line bg-surface-overlay p-4 sm:p-5">
            <div className="flex items-center gap-2">
              <Swords className="size-5 text-accent" />
              <h2 className="font-semibold">
                {t('home.assistantPreview.promptTitle')}
              </h2>
            </div>

            <p className="mt-1 text-sm text-content-secondary">
              {t('home.assistantPreview.promptHelp')}
            </p>

            <div className="mt-4 space-y-2">
              {starterSearches.map((prompt) => (
                <button
                  key={prompt.key}
                  type="button"
                  onClick={() => {
                    setSection(prompt.section);
                    setQuery(prompt.query);
                  }}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-line bg-surface-raised px-3 py-3 text-left text-sm transition hover:border-primary/50 hover:bg-surface-active"
                >
                  <span>{prompt.label}</span>
                  <ArrowRight className="size-4 shrink-0 text-primary" />
                </button>
              ))}
            </div>

            <p className="mt-4 rounded-xl bg-accent/10 p-3 text-xs text-content-secondary">
              {t('home.assistantPreview.futureHelp')}
            </p>
          </aside>
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
                to={`/quests/${encodeURIComponent(entry.questId)}`}
                className="min-w-0"
              >
                <Card className="h-full p-4 transition hover:border-primary/50">
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
          <h2 id="home-search-options" className="text-lg font-semibold">
            {t('home.assistantPreview.exploreTitle')}
          </h2>
          <p className="text-sm text-content-muted">
            {t('home.assistantPreview.exploreHelp')}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {searchOptions.map((option) => {
            const Icon = option.icon;

            return (
              <Link key={option.key} to={option.to}>
                <Card className="h-full p-4 transition hover:border-primary/50">
                  <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-3 font-semibold">{option.title}</h3>
                  <p className="mt-1 text-sm text-content-secondary">
                    {option.help}
                  </p>
                </Card>
              </Link>
            );
          })}
        </div>
      </Section>
    </Page>
  );
}
