import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useId,
  useState,
} from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  BookOpen,
  Gem,
  Loader2,
  MapPin,
  Search,
  Shield,
  Sparkles,
} from 'lucide-react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  questsApi,
} from '../../services/api';

export type KnowledgeSearchSection =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones';

export interface KnowledgeSuggestion {
  key: string;
  section: KnowledgeSearchSection;
  label: string;
  subtitle: string;
  to: string;
  imageUrl?: string;
}

interface KnowledgeSearchBoxProps {
  section: KnowledgeSearchSection;
  query: string;
  onSectionChange: (section: KnowledgeSearchSection) => void;
  onQueryChange: (query: string) => void;
}

const sectionIcons: Record<KnowledgeSearchSection, LucideIcon> = {
  creatures: BookOpen,
  bosses: Shield,
  items: Gem,
  quests: BookOpen,
  zones: MapPin,
};

const normalize = (value: string) =>
  value.trim().toLocaleLowerCase().replace(/\s+/g, ' ');

const fallbackUrl = (
  section: KnowledgeSearchSection,
  query: string,
): string => {
  const params = new URLSearchParams({ tab: section });

  if (query.trim()) {
    params.set('q', query.trim());
  }

  return `/cyclopedia?${params.toString()}`;
};

async function loadSuggestions(
  section: KnowledgeSearchSection,
  query: string,
  signal: AbortSignal,
  t: TFunction,
): Promise<KnowledgeSuggestion[]> {
  if (section === 'creatures') {
    const rows = await creaturesApi.getAll(
      {
        search: query,
        is_boss: false,
        skip: 0,
        limit: 6,
      },
      signal,
    );

    return rows
      .filter((row) => !row.is_boss)
      .map((row) => ({
        key: `creature:${row.id}`,
        section,
        label: row.name,
        subtitle: t('home.searchSuggestions.creatureStats', {
          hp: row.hitpoints.toLocaleString(),
          exp: row.experience.toLocaleString(),
        }),
        to: `/creatures/${row.slug || row.id}`,
        imageUrl: `/api/v1/creatures/${row.id}/image`,
      }));
  }

  if (section === 'bosses') {
    const rows = await creaturesApi.getBosses(
      {
        search: query,
        skip: 0,
        limit: 6,
      },
      signal,
    );

    return rows.map((row) => ({
      key: `boss:${row.id}`,
      section,
      label: row.name,
      subtitle:
        row.difficulty ||
        t('home.searchSuggestions.types.boss'),
      to: `/creatures/${row.slug || row.id}`,
      imageUrl: `/api/v1/creatures/${row.id}/image`,
    }));
  }

  if (section === 'items') {
    const rows = await itemsApi.search(query, 6, signal);

    return rows.map((row) => {
      const imageId = row.image_item_id ?? row.id;

      return {
        key: `item:${row.normalized_name}`,
        section,
        label: row.item_name,
        subtitle:
          row.category ||
          row.item_type ||
          t('home.searchSuggestions.types.item'),
        to: fallbackUrl(section, row.item_name),
        imageUrl:
          imageId != null
            ? `/api/v1/items/${imageId}/image`
            : undefined,
      };
    });
  }

  if (section === 'quests') {
    const rows = await questsApi.search(query, 6, signal);

    return rows.map((row) => ({
      key: `quest:${row.id || row.slug || row.name}`,
      section,
      label: row.name,
      subtitle:
        row.group_name ||
        row.location ||
        t('home.searchSuggestions.types.quest'),
      to:
        row.id != null
          ? `/quests/${row.id}`
          : fallbackUrl(section, row.name),
    }));
  }

  const rows = await huntZonesApi.getAll(
    {
      search: query,
      skip: 0,
      limit: 6,
    },
    signal,
  );

  return rows.map((row) => ({
    key: `zone:${row.id}`,
    section,
    label: row.name,
    subtitle: t('home.searchSuggestions.zoneMeta', {
      place:
        row.city ||
        row.region ||
        t('home.searchSuggestions.types.zone'),
      level: row.recommended_level || row.min_level || 0,
    }),
    to: fallbackUrl(section, row.name),
    imageUrl: `/api/v1/hunt-zones/${row.id}/map-image`,
  }));
}

export default function KnowledgeSearchBox({
  section,
  query,
  onSectionChange,
  onQueryChange,
}: KnowledgeSearchBoxProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const listId = useId();

  const [suggestions, setSuggestions] = useState<KnowledgeSuggestion[]>(
    [],
  );
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    const normalizedQuery = query.trim();

    setActiveIndex(-1);

    if (normalizedQuery.length < 2) {
      setSuggestions([]);
      setLoading(false);
      setOpen(false);
      return undefined;
    }

    const controller = new AbortController();

    const timer = window.setTimeout(() => {
      setLoading(true);

      void loadSuggestions(
        section,
        normalizedQuery,
        controller.signal,
        t,
      )
        .then((rows) => {
          setSuggestions(rows);
          setOpen(true);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setSuggestions([]);
            setOpen(true);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setLoading(false);
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, section, t]);

  const openSuggestion = (suggestion: KnowledgeSuggestion) => {
    setOpen(false);
    setActiveIndex(-1);
    navigate(suggestion.to);
  };

  const exactSuggestion = (
    rows: KnowledgeSuggestion[],
    value: string,
  ) =>
    rows.find(
      (suggestion) =>
        normalize(suggestion.label) === normalize(value),
    );

  const submit = async (event: FormEvent) => {
    event.preventDefault();

    const normalizedQuery = query.trim();

    if (!normalizedQuery) {
      navigate(fallbackUrl(section, ''));
      return;
    }

    const selected =
      activeIndex >= 0 ? suggestions[activeIndex] : undefined;

    if (selected) {
      openSuggestion(selected);
      return;
    }

    const currentExact = exactSuggestion(
      suggestions,
      normalizedQuery,
    );

    if (currentExact) {
      openSuggestion(currentExact);
      return;
    }

    if (normalizedQuery.length >= 2) {
      const controller = new AbortController();

      setLoading(true);

      try {
        const freshSuggestions = await loadSuggestions(
          section,
          normalizedQuery,
          controller.signal,
          t,
        );

        const freshExact = exactSuggestion(
          freshSuggestions,
          normalizedQuery,
        );

        if (freshExact) {
          openSuggestion(freshExact);
          return;
        }
      } catch {
        // Fall through to the complete Cyclopedia result page.
      } finally {
        setLoading(false);
      }
    }

    navigate(fallbackUrl(section, normalizedQuery));
  };

  const handleKeyboard = (
    event: KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        suggestions.length
          ? (current + 1) % suggestions.length
          : -1,
      );
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        suggestions.length
          ? (current - 1 + suggestions.length) %
            suggestions.length
          : -1,
      );
      return;
    }

    if (event.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="grid gap-2 rounded-2xl border border-line bg-surface-overlay p-2 sm:grid-cols-[10rem_minmax(0,1fr)_auto]"
      role="search"
    >
      <select
        aria-label={t('home.assistantPreview.section')}
        value={section}
        onChange={(event) => {
          onSectionChange(
            event.target.value as KnowledgeSearchSection,
          );
          setSuggestions([]);
          setOpen(false);
        }}
        className="ds-select"
      >
        <option value="creatures">
          {t(
            'home.assistantPreview.categories.creatures.title',
          )}
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

      <div className="relative min-w-0">
        <label className="relative block">
          <span className="sr-only">
            {t('home.assistantPreview.searchLabel')}
          </span>

          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />

          <input
            className="app-input w-full pl-9"
            value={query}
            autoComplete="off"
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls={listId}
            aria-activedescendant={
              activeIndex >= 0
                ? `${listId}-${activeIndex}`
                : undefined
            }
            onFocus={() => {
              if (query.trim().length >= 2) {
                setOpen(true);
              }
            }}
            onBlur={() => {
              window.setTimeout(() => setOpen(false), 120);
            }}
            onKeyDown={handleKeyboard}
            onChange={(event) =>
              onQueryChange(event.target.value)
            }
            placeholder={t(
              'home.assistantPreview.placeholder',
            )}
          />
        </label>

        {open ? (
          <div
            id={listId}
            role="listbox"
            aria-label={t(
              'home.searchSuggestions.listLabel',
            )}
            className="absolute left-0 right-0 top-[calc(100%+.5rem)] z-50 max-h-80 overflow-y-auto rounded-2xl border border-line bg-surface-overlay p-2 shadow-2xl"
          >
            {loading && suggestions.length === 0 ? (
              <div className="flex items-center gap-2 px-3 py-4 text-sm text-content-muted">
                <Loader2 className="size-4 animate-spin" />
                {t('home.searchSuggestions.loading')}
              </div>
            ) : null}

            {!loading && suggestions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-content-muted">
                {t('home.searchSuggestions.empty')}
              </div>
            ) : null}

            {suggestions.map((suggestion, index) => (
              <button
                id={`${listId}-${index}`}
                key={suggestion.key}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => {
                  event.preventDefault();
                  openSuggestion(suggestion);
                }}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition ${
                  index === activeIndex
                    ? 'bg-primary/10 text-content-primary'
                    : 'hover:bg-surface-active'
                }`}
              >
                <SuggestionMedia suggestion={suggestion} />

                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-sm">
                    {suggestion.label}
                  </strong>
                  <span className="block truncate text-xs text-content-muted">
                    {suggestion.subtitle}
                  </span>
                </span>

                <span className="text-xs font-semibold text-primary">
                  {t('home.searchSuggestions.open')}
                </span>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <button
        className="app-button-primary"
        type="submit"
        disabled={loading}
      >
        {loading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Sparkles className="size-4" />
        )}
        {t('home.assistantPreview.search')}
      </button>
    </form>
  );
}

function SuggestionMedia({
  suggestion,
}: {
  suggestion: KnowledgeSuggestion;
}) {
  const Icon = sectionIcons[suggestion.section];
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [suggestion.imageUrl]);

  return (
    <span className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/10 text-primary">
      {suggestion.imageUrl && !failed ? (
        <img
          src={suggestion.imageUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          onError={() => setFailed(true)}
          className="size-10 object-contain [image-rendering:pixelated]"
        />
      ) : (
        <Icon className="size-5" aria-hidden="true" />
      )}
    </span>
  );
}
