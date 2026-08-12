import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import {
  Loader2,
  Search,
  Sparkles,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  questsApi,
} from '../../services/api';
import KnowledgeCategoryIcon from '../knowledge/KnowledgeCategoryIcon';
import { buildKnowledgeSearchPath } from '../../utils/cyclopediaNavigation';

export type KnowledgeSearchSection =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones';

type KnowledgeSuggestionKind =
  | 'creature'
  | 'boss'
  | 'item'
  | 'quest'
  | 'zone';

export interface KnowledgeSuggestion {
  key: string;
  section: KnowledgeSearchSection;
  kind: KnowledgeSuggestionKind;
  label: string;
  to: string;
  imageUrl?: string;
}

interface KnowledgeSearchBoxProps {
  section: KnowledgeSearchSection;
  query: string;
  onSectionChange: (section: KnowledgeSearchSection) => void;
  onQueryChange: (query: string) => void;
  onSuggestionSelect?: (
    suggestion: KnowledgeSuggestion,
  ) => void;
  showSectionSelect?: boolean;
  submitLabel?: string;
  externalSuggestions?: KnowledgeSuggestion[];
  externalLoading?: boolean;
  compact?: boolean;
}

const CACHE_STORAGE_KEY =
  'tibiahub:knowledge-search-suggestions:v2';
const CACHE_SEPARATOR = '\u0000';
const MAX_CACHE_ENTRIES = 32;
const MAX_REMOTE_RESULTS = 50;
const MAX_VISIBLE_SUGGESTIONS = 8;

const suggestionCache = new Map<
  string,
  KnowledgeSuggestion[]
>();

let cacheHydrated = false;

const normalize = (value: string) =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLocaleLowerCase()
    .replace(/\s+/g, ' ');

const cacheKey = (
  section: KnowledgeSearchSection,
  query: string,
) => `${section}${CACHE_SEPARATOR}${normalize(query)}`;

const fallbackUrl = (
  section: KnowledgeSearchSection,
  query: string,
): string => buildKnowledgeSearchPath(section, query);

function hydrateSuggestionCache() {
  if (cacheHydrated) {
    return;
  }

  cacheHydrated = true;

  try {
    const raw = sessionStorage.getItem(CACHE_STORAGE_KEY);

    if (!raw) {
      return;
    }

    const stored = JSON.parse(raw) as Record<
      string,
      KnowledgeSuggestion[]
    >;

    for (const [key, suggestions] of Object.entries(stored)) {
      if (Array.isArray(suggestions)) {
        suggestionCache.set(key, suggestions);
      }
    }
  } catch {
    sessionStorage.removeItem(CACHE_STORAGE_KEY);
  }
}

function persistSuggestionCache() {
  try {
    sessionStorage.setItem(
      CACHE_STORAGE_KEY,
      JSON.stringify(Object.fromEntries(suggestionCache)),
    );
  } catch {
    // Search continues with the in-memory cache.
  }
}

function storeSuggestions(
  section: KnowledgeSearchSection,
  query: string,
  suggestions: KnowledgeSuggestion[],
) {
  const key = cacheKey(section, query);

  suggestionCache.delete(key);
  suggestionCache.set(key, suggestions);

  while (suggestionCache.size > MAX_CACHE_ENTRIES) {
    const oldestKey = suggestionCache.keys().next().value;

    if (typeof oldestKey !== 'string') {
      break;
    }

    suggestionCache.delete(oldestKey);
  }

  persistSuggestionCache();
}

function suggestionRank(
  query: string,
  suggestion: KnowledgeSuggestion,
) {
  const normalizedQuery = normalize(query);
  const normalizedLabel = normalize(suggestion.label);

  if (normalizedLabel === normalizedQuery) {
    return 0;
  }

  if (normalizedLabel.startsWith(normalizedQuery)) {
    return 1;
  }

  if (normalizedLabel.includes(normalizedQuery)) {
    return 2;
  }

  return 3;
}

function rankSuggestions(
  query: string,
  suggestions: KnowledgeSuggestion[],
) {
  return suggestions
    .map((suggestion) => ({
      suggestion,
      rank: suggestionRank(query, suggestion),
      normalizedLabel: normalize(suggestion.label),
    }))
    .filter(({ rank }) => rank < 3)
    .sort(
      (left, right) =>
        left.rank - right.rank ||
        left.normalizedLabel.length -
          right.normalizedLabel.length ||
        left.normalizedLabel.localeCompare(
          right.normalizedLabel,
        ),
    )
    .map(({ suggestion }) => suggestion);
}

function cachedSuggestionsFor(
  section: KnowledgeSearchSection,
  query: string,
): KnowledgeSuggestion[] | null {
  hydrateSuggestionCache();

  const exact = suggestionCache.get(cacheKey(section, query));

  if (exact) {
    return rankSuggestions(query, exact);
  }

  const normalizedQuery = normalize(query);
  const prefix = `${section}${CACHE_SEPARATOR}`;

  const ancestors = [...suggestionCache.entries()]
    .filter(([key]) => key.startsWith(prefix))
    .map(([key, suggestions]) => ({
      cachedQuery: key.slice(prefix.length),
      suggestions,
    }))
    .filter(
      ({ cachedQuery }) =>
        cachedQuery.length >= 2 &&
        normalizedQuery.startsWith(cachedQuery),
    )
    .sort(
      (left, right) =>
        right.cachedQuery.length - left.cachedQuery.length,
    );

  for (const ancestor of ancestors) {
    const filtered = rankSuggestions(
      normalizedQuery,
      ancestor.suggestions,
    );

    if (filtered.length >= 3) {
      return filtered;
    }
  }

  return null;
}

async function loadRemoteSuggestions(
  section: KnowledgeSearchSection,
  query: string,
  signal: AbortSignal,
): Promise<KnowledgeSuggestion[]> {
  if (section === 'creatures') {
    const rows = await creaturesApi.getAll(
      {
        search: query,
        is_boss: false,
        skip: 0,
        limit: MAX_REMOTE_RESULTS,
      },
      signal,
    );

    return rows
      .filter((row) => !row.is_boss)
      .map((row) => ({
        key: `creature:${row.id}`,
        section,
        kind: 'creature',
        label: row.name,
        to: `/creatures/${row.slug || row.id}`,
        imageUrl:
          `/api/v1/creatures/${row.id}/image` +
          '?placeholder=false',
      }));
  }

  if (section === 'bosses') {
    const rows = await creaturesApi.getBosses(
      {
        search: query,
        skip: 0,
        limit: MAX_REMOTE_RESULTS,
      },
      signal,
    );

    return rows.map((row) => ({
      key: `boss:${row.id}`,
      section,
      kind: 'boss',
      label: row.name,
      to: `/creatures/${row.slug || row.id}`,
      imageUrl:
        `/api/v1/creatures/${row.id}/image` +
        '?placeholder=false',
    }));
  }

  if (section === 'items') {
    const rows = await itemsApi.search(
      query,
      MAX_REMOTE_RESULTS,
      signal,
    );

    return rows.map((row) => {
      const imageId = row.image_item_id ?? row.id;

      return {
        key: `item:${row.normalized_name}`,
        section,
        kind: 'item',
        label: row.item_name,
        to: `/items/${row.slug || row.normalized_name.split(' ').join('-')}`,
        imageUrl:
          imageId != null
            ? `/api/v1/items/${imageId}/image` +
              '?placeholder=false'
            : undefined,
      };
    });
  }

  if (section === 'quests') {
    const rows = await questsApi.search(
      query,
      MAX_REMOTE_RESULTS,
      signal,
    );

    return rows.map((row) => ({
      key: `quest:${row.id || row.slug || row.name}`,
      section,
      kind: 'quest',
      label: row.name,
      to:
        row.slug || row.id != null
          ? `/quests/${row.slug || row.id}`
          : fallbackUrl(section, row.name),
    }));
  }

  const rows = await huntZonesApi.getAll(
    {
      search: query,
      skip: 0,
      limit: MAX_REMOTE_RESULTS,
    },
    signal,
  );

  return rows.map((row) => ({
    key: `zone:${row.id}`,
    section,
    kind: 'zone',
    label: row.name,
    to: `/hunt-zones/${row.slug || row.id}`,
    imageUrl: `/api/v1/hunt-zones/${row.id}/map-image`,
  }));
}

async function loadSuggestions(
  section: KnowledgeSearchSection,
  query: string,
  signal: AbortSignal,
): Promise<KnowledgeSuggestion[]> {
  const cached = cachedSuggestionsFor(section, query);

  if (cached) {
    return cached.slice(0, MAX_VISIBLE_SUGGESTIONS);
  }

  const remote = await loadRemoteSuggestions(
    section,
    query,
    signal,
  );

  storeSuggestions(section, query, remote);

  return rankSuggestions(query, remote).slice(
    0,
    MAX_VISIBLE_SUGGESTIONS,
  );
}

export default function KnowledgeSearchBox({
  section,
  query,
  onSectionChange,
  onQueryChange,
  onSuggestionSelect,
  showSectionSelect = true,
  submitLabel,
  externalSuggestions,
  externalLoading = false,
  compact = false,
}: KnowledgeSearchBoxProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const listId = useId();
  const closeOnBlurRef = useRef(true);

  const [suggestions, setSuggestions] = useState<
    KnowledgeSuggestion[]
  >([]);
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

    if (externalSuggestions !== undefined) {
      setLoading(externalLoading);
      setSuggestions(
        externalLoading
          ? []
          : rankSuggestions(
              normalizedQuery,
              externalSuggestions,
            ).slice(0, MAX_VISIBLE_SUGGESTIONS),
      );
      setOpen(true);
      return undefined;
    }

    const controller = new AbortController();

    const timer = window.setTimeout(() => {
      setLoading(true);

      void loadSuggestions(
        section,
        normalizedQuery,
        controller.signal,
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
    }, 220);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    query,
    section,
    externalLoading,
    externalSuggestions,
  ]);

  const openSuggestion = (
    suggestion: KnowledgeSuggestion,
  ) => {
    setOpen(false);
    setActiveIndex(-1);
    if (onSuggestionSelect) {
      onSuggestionSelect(suggestion);
      return;
    }
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

    if (externalSuggestions !== undefined) {
      navigate(fallbackUrl(section, normalizedQuery));
      return;
    }

    const controller = new AbortController();

    setLoading(true);

    try {
      const freshSuggestions = await loadSuggestions(
        section,
        normalizedQuery,
        controller.signal,
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
      // Continue to the complete Cyclopedia result page.
    } finally {
      setLoading(false);
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
      return;
    }

    if (
      event.key === 'Enter' &&
      open &&
      activeIndex >= 0 &&
      suggestions[activeIndex]
    ) {
      event.preventDefault();
      openSuggestion(suggestions[activeIndex]);
    }
  };

  const clearQuery = () => {
    onQueryChange('');
    setSuggestions([]);
    setOpen(false);
    setActiveIndex(-1);
  };

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className={`grid border border-line bg-surface-overlay ${
        compact
          ? 'gap-1 rounded-xl p-1'
          : 'gap-2 rounded-2xl p-2'
      } ${
        showSectionSelect
          ? 'sm:grid-cols-[10rem_minmax(0,1fr)_auto]'
          : compact
            ? 'sm:grid-cols-1'
            : 'sm:grid-cols-[minmax(0,1fr)_auto]'
      }`}
      role="search"
    >
      {showSectionSelect ? (
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
      ) : null}

      <div className="relative min-w-0">
        <label className="relative block">
          <span className="sr-only">
            {t('home.assistantPreview.searchLabel')}
          </span>

          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />

          <input
            className={`app-input w-full pl-9 ${
              compact
                ? 'h-9 py-1 pr-10 text-sm'
                : 'pr-10'
            }`}
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
              if (!closeOnBlurRef.current) {
                closeOnBlurRef.current = true;
                return;
              }
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

          {query.trim().length > 0 ? (
            <button
              type="button"
              title={t('cyclopedia.filters.clearSearch')}
              aria-label={t('cyclopedia.filters.clearSearch')}
              onClick={clearQuery}
              className="absolute right-2 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-content-muted transition hover:bg-surface-hover hover:text-content-primary"
            >
              <span aria-hidden="true">×</span>
            </button>
          ) : null}
        </label>

        {open ? (
          <div
            id={listId}
            role="listbox"
            aria-label={t(
              'home.assistantPreview.searchSuggestions.listLabel',
            )}
            className="absolute left-0 right-0 top-[calc(100%+.5rem)] z-50 max-h-96 overflow-y-auto rounded-2xl border border-line bg-surface-overlay p-2 shadow-2xl"
          >
            {loading && suggestions.length === 0 ? (
              <div className="flex items-center gap-2 px-3 py-4 text-sm text-content-muted">
                <Loader2 className="size-4 animate-spin" />
                {t(
                  'home.assistantPreview.searchSuggestions.loading',
                )}
              </div>
            ) : null}

            {!loading && suggestions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-content-muted">
                {t(
                  'home.assistantPreview.searchSuggestions.empty',
                )}
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
                onPointerDown={(event) => {
                  event.preventDefault();
                  closeOnBlurRef.current = false;
                }}
                onClick={() => {
                  openSuggestion(suggestion);
                }}
                onKeyDown={(event) => {
                  if (
                    event.key === 'Enter' ||
                    event.key === ' '
                  ) {
                    event.preventDefault();
                    openSuggestion(suggestion);
                  }
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
                    {t(
                      `home.assistantPreview.searchSuggestions.types.${suggestion.kind}`,
                    )}
                  </span>
                </span>

                <span className="text-xs font-semibold text-primary">
                  {t(
                    'home.assistantPreview.searchSuggestions.open',
                  )}
                </span>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <button
        className={
          compact
            ? 'sr-only'
            : 'app-button-primary'
        }
        type="submit"
        disabled={loading}
      >
        {loading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Sparkles className="size-4" />
        )}

        {submitLabel || t('home.assistantPreview.search')}
      </button>
    </form>
  );
}

function SuggestionMedia({
  suggestion,
}: {
  suggestion: KnowledgeSuggestion;
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [suggestion.imageUrl]);

  return (
    <span className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/10 text-primary">
      {suggestion.imageUrl && !failed ? (
        <img
          src={suggestion.imageUrl}
          alt=""
          aria-hidden="true"
          loading="eager"
          decoding="async"
          onError={() => setFailed(true)}
          className="size-11 object-contain p-0.5 [image-rendering:pixelated]"
        />
      ) : (
        <KnowledgeCategoryIcon category={suggestion.section} label={suggestion.label} className="size-12" mediaClassName="size-11 p-0.5" />
      )}
    </span>
  );
}
