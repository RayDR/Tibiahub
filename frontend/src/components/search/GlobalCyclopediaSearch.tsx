import { useEffect, useMemo, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import BrandCategoryFallbackIcon, { type BrandCategoryKey } from '../icons/BrandCategoryFallbackIcon';
import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  namedKnowledgeApi,
  questsApi,
} from '../../services/api';
import { availableItemMediaUrl } from '../../utils/entityMedia';
import { localNpcMediaUrl } from '../../utils/npcCyclopedia';

type ResultKind = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones' | 'npcs';

interface SearchResult {
  key: string;
  kind: ResultKind;
  label: string;
  subtitle?: string;
  to: string;
  imageUrl?: string;
}

const resultLimit = 4;

const categoryLabel = (kind: ResultKind): string => ({
  creatures: 'Creatures',
  bosses: 'Bosses',
  items: 'Loot',
  quests: 'Quests',
  zones: 'Hunt Zones',
  npcs: 'NPCs',
})[kind];

export default function GlobalCyclopediaSearch({ className = '' }: { className?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (event.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };
    window.addEventListener('keydown', onShortcut);
    return () => window.removeEventListener('keydown', onShortcut);
  }, []);

  useEffect(() => {
    requestRef.current?.abort();
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResults([]);
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const [creatures, bosses, items, quests, zones, npcPage] = await Promise.all([
          creaturesApi.getAll({ search: normalized, limit: resultLimit, is_boss: false }, controller.signal),
          creaturesApi.getBosses({ search: normalized, limit: resultLimit }, controller.signal),
          itemsApi.search(normalized, resultLimit, controller.signal),
          questsApi.search(normalized, resultLimit, controller.signal),
          huntZonesApi.getAll({ search: normalized, limit: resultLimit }, controller.signal),
          namedKnowledgeApi.listNpcs({ search: normalized, limit: resultLimit }, controller.signal),
        ]);
        if (controller.signal.aborted) return;

        setResults([
          ...creatures.map((row) => ({
            key: `creature:${row.id}`,
            kind: 'creatures' as const,
            label: row.name,
            subtitle: row.classification || row.difficulty || undefined,
            to: `/creatures/${row.slug || row.id}`,
            imageUrl: `/api/v1/creatures/${row.id}/image?placeholder=false`,
          })),
          ...bosses.map((row) => ({
            key: `boss:${row.id}`,
            kind: 'bosses' as const,
            label: row.name,
            subtitle: row.difficulty || undefined,
            to: `/creatures/${row.slug || row.id}`,
            imageUrl: `/api/v1/creatures/${row.id}/image?placeholder=false`,
          })),
          ...items.map((row) => ({
            key: `item:${row.id || row.normalized_name}`,
            kind: 'items' as const,
            label: row.item_name,
            subtitle: row.item_type || row.category || undefined,
            to: `/items/${row.slug || row.normalized_name.split(' ').join('-')}`,
            imageUrl: availableItemMediaUrl(row.media) || undefined,
          })),
          ...quests.map((row) => ({
            key: `quest:${row.id || row.slug || row.name}`,
            kind: 'quests' as const,
            label: row.name,
            subtitle: row.group_name || row.category || undefined,
            to: row.slug || row.id ? `/quests/${row.slug || row.id}` : `/cyclopedia?tab=quests&q=${encodeURIComponent(row.name)}`,
          })),
          ...zones.map((row) => ({
            key: `zone:${row.id}`,
            kind: 'zones' as const,
            label: row.name,
            subtitle: row.region || row.city || undefined,
            to: `/hunt-zones/${row.slug || row.id}`,
            imageUrl: `/api/v1/hunt-zones/${row.id}/map-image?placeholder=false`,
          })),
          ...npcPage.items.map((row) => ({
            key: `npc:${row.canonical_id}`,
            kind: 'npcs' as const,
            label: row.name,
            subtitle: row.title || row.occupation || row.location_name || undefined,
            to: `/npcs/${row.canonical_id}`,
            imageUrl: localNpcMediaUrl(row.media) || undefined,
          })),
        ]);
      } catch (error: any) {
        if (error?.name !== 'CanceledError' && error?.code !== 'ERR_CANCELED') setResults([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 260);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const grouped = useMemo(() => {
    const map = new Map<ResultKind, SearchResult[]>();
    for (const row of results) map.set(row.kind, [...(map.get(row.kind) || []), row]);
    return map;
  }, [results]);

  const choose = (result: SearchResult) => {
    setOpen(false);
    setQuery('');
    navigate(result.to);
  };

  return (
    <div className={`relative min-w-0 ${className}`}>
      <div className="app-global-search-field flex items-center gap-2 rounded-lg border border-line bg-surface-base/60 px-3">
        <Search className="size-4 shrink-0 text-content-muted" aria-hidden="true" />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          aria-label={t('nav.search', { defaultValue: 'Search TibiaHub' })}
          placeholder={t('cyclopedia.globalSearch.placeholder', { defaultValue: 'Search anything...' })}
          className="h-10 min-w-0 flex-1 bg-transparent text-sm text-content-primary outline-none placeholder:text-content-muted"
        />
        {query ? <button type="button" onClick={() => setQuery('')} className="grid size-7 place-items-center rounded text-content-muted hover:text-content-primary" aria-label={t('common.clear', { defaultValue: 'Clear' })}><X className="size-3.5" /></button> : <kbd className="hidden rounded border border-line bg-surface-raised px-1.5 py-0.5 text-[10px] text-content-muted xl:inline">Ctrl K</kbd>}
      </div>

      {open && query.trim().length >= 2 ? (
        <div className="ds-dropdown app-global-search-results absolute left-0 right-0 top-full mt-2 max-h-[70vh] overflow-y-auto p-2">
          {loading && results.length === 0 ? <div className="px-3 py-5 text-center text-xs text-content-muted">{t('common.loading')}</div> : null}
          {!loading && results.length === 0 ? <div className="px-3 py-5 text-center text-xs text-content-muted">{t('common.noResults', { defaultValue: 'No results' })}</div> : null}
          {[...grouped.entries()].map(([kind, rows]) => (
            <section key={kind} className="mb-2 last:mb-0">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">{categoryLabel(kind)}</div>
              {rows.map((row) => (
                <button key={row.key} type="button" onClick={() => choose(row)} className="flex min-h-12 w-full items-center gap-3 rounded-md px-2 py-1.5 text-left hover:bg-surface-hover">
                  {row.imageUrl ? (
                    <ImageWithFallback src={row.imageUrl} alt="" className="size-9 object-contain [image-rendering:pixelated]" containerClassName="grid size-10 shrink-0 place-items-center" fallbackKind={kind === 'bosses' ? 'boss' : kind === 'items' ? 'item' : kind === 'npcs' ? 'npc' : 'creature'} fallbackLabel={row.label} />
                  ) : (
                    <span className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary"><BrandCategoryFallbackIcon category={kind as BrandCategoryKey} className="size-5" /></span>
                  )}
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-content-primary">{row.label}</span>{row.subtitle ? <span className="block truncate text-xs text-content-muted">{row.subtitle}</span> : null}</span>
                </button>
              ))}
            </section>
          ))}
        </div>
      ) : null}
    </div>
  );
}
