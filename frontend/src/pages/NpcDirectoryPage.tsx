import { ArrowUpRight, BookOpenCheck, Coins, Map, MapPin, Search, UserRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';

import { Badge, EmptyState, ErrorState, LoadingState, Page, PageHeader, PaginationControls } from '../components/ui';
import { namedKnowledgeApi } from '../services/api';
import type { NpcDirectoryItem, NpcDirectoryPage as NpcDirectoryPayload } from '../types';
import { buildMapEntityUrl } from '../services/tibiaMap';
import { useSeoMetadata } from '../utils/seo';

const PAGE_SIZE = 24;

function Fact({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return <span className="inline-flex min-h-7 items-center gap-1.5 text-xs text-content-secondary">{icon}{children}</span>;
}

function knownCount(value: number | null | undefined, none: string, unknown: string, count: (value: number) => string) {
  if (value == null) return unknown;
  return value === 0 ? none : count(value);
}

function NpcCard({ npc }: { npc: NpcDirectoryItem }) {
  const { t } = useTranslation();
  const detailPath = `/npcs/${npc.canonical_id}`;
  const mapPath = buildMapEntityUrl({
    entityType: 'npc', canonicalEntityId: npc.canonical_id, name: npc.name, slug: npc.slug,
  });
  return <article className="group flex min-h-full flex-col rounded-2xl border border-line bg-surface-base/70 p-4 transition hover:border-primary/40 hover:bg-surface-raised">
    <div className="flex min-w-0 items-start gap-3">
      <div className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-xl border border-line bg-primary/10 text-primary">
        {npc.media.status === 'available' && npc.media.url
          ? <img src={npc.media.url} alt="" loading="lazy" decoding="async" className="size-full object-contain [image-rendering:pixelated]" />
          : <UserRound className="size-7" aria-hidden="true" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-content-muted">{t('npcDirectory.card.eyebrow')}</p>
        <h2 className="truncate text-lg font-bold text-content-primary">{npc.name}</h2>
        {(npc.title || npc.occupation) && <p className="line-clamp-2 text-sm text-content-secondary">{npc.title || npc.occupation}</p>}
      </div>
    </div>
    <div className="mt-4 flex flex-col gap-1.5">
      <Fact icon={<MapPin className="size-3.5 text-primary" />}><span className="line-clamp-1">{npc.location_name || t('npcDirectory.unknown.location')}</span></Fact>
      <Fact icon={<Coins className="size-3.5 text-primary" />}>
        {knownCount(npc.buys_count, t('npcDirectory.none.buys'), t('npcDirectory.unknown.buys'), count => t('npcDirectory.count.buys', { count }))}
        <span aria-hidden="true">·</span>
        {knownCount(npc.sells_count, t('npcDirectory.none.sells'), t('npcDirectory.unknown.sells'), count => t('npcDirectory.count.sells', { count }))}
      </Fact>
      <Fact icon={<BookOpenCheck className="size-3.5 text-primary" />}>{knownCount(npc.quest_count, t('npcDirectory.none.quests'), t('npcDirectory.unknown.quests'), count => t('npcDirectory.count.quests', { count }))}</Fact>
    </div>
    <div className="mt-4 flex flex-wrap gap-2">
      {npc.map_available ? <Badge tone="success"><Map className="size-3" />{t('npcDirectory.card.mapped')}</Badge> : <Badge>{t('npcDirectory.card.mapPending')}</Badge>}
      {npc.destination_count != null && npc.destination_count > 0 ? <Badge tone="info">{t('npcDirectory.count.destinations', { count: npc.destination_count })}</Badge> : null}
    </div>
    <div className="mt-auto flex flex-wrap gap-2 pt-5">
      <Link to={detailPath} className="app-button-primary app-button-sm flex-1 justify-center">{t('npcDirectory.card.open')}<ArrowUpRight className="size-4" /></Link>
      {npc.map_available ? <Link to={mapPath} className="app-button-secondary app-button-sm" aria-label={t('npcDirectory.card.openMapFor', { name: npc.name })}><Map className="size-4" /></Link> : null}
    </div>
  </article>;
}

export default function NpcDirectoryPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const requestedSearch = params.get('q') || '';
  const requestedLocation = params.get('location') || '';
  const requestedPage = Math.max(1, Number(params.get('page')) || 1);
  const [search, setSearch] = useState(requestedSearch);
  const [locationFilter, setLocationFilter] = useState(requestedLocation);
  const [payload, setPayload] = useState<NpcDirectoryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const skip = (requestedPage - 1) * PAGE_SIZE;

  useSeoMetadata({
    title: t('npcDirectory.seoTitle'),
    description: t('npcDirectory.seoDescription'),
    canonicalPath: '/npcs',
  });

  useEffect(() => setSearch(requestedSearch), [requestedSearch]);
  useEffect(() => setLocationFilter(requestedLocation), [requestedLocation]);

  useEffect(() => {
    if (requestedSearch.length === 1) {
      setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    void namedKnowledgeApi.listNpcs({
      search: requestedSearch || undefined,
      location: requestedLocation || undefined,
      skip,
      limit: PAGE_SIZE,
    }, controller.signal).then(setPayload).catch(error => {
      if (error?.name !== 'CanceledError') setFailed(true);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [requestedLocation, requestedSearch, reloadKey, skip]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      const trimmed = search.trim();
      if (trimmed.length === 1) return;
      if (trimmed) next.set('q', trimmed); else next.delete('q');
      const trimmedLocation = locationFilter.trim();
      if (trimmedLocation) next.set('location', trimmedLocation); else next.delete('location');
      next.delete('page');
      if (next.toString() !== params.toString()) setParams(next, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [locationFilter, params, search, setParams]);

  const resultLabel = useMemo(() => t('npcDirectory.resultCount', { count: payload?.total || 0 }), [payload?.total, t]);
  const changePage = (nextSkip: number) => {
    const next = new URLSearchParams(params);
    const page = Math.floor(nextSkip / PAGE_SIZE) + 1;
    if (page > 1) next.set('page', String(page)); else next.delete('page');
    setParams(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return <Page>
    <PageHeader
      eyebrow={t('npcDirectory.eyebrow')}
      title={t('npcDirectory.title')}
      subtitle={t('npcDirectory.subtitle')}
      iconElement={<UserRound className="size-7" />}
      breadcrumbs={[{ label: t('nav.search'), to: '/cyclopedia' }, { label: t('npcDirectory.title') }]}
    />
    <section aria-label={t('npcDirectory.searchLabel')} className="mb-6 rounded-2xl border border-line bg-surface-base/70 p-4">
      <label htmlFor="npc-directory-search" className="text-sm font-semibold text-content-primary">{t('npcDirectory.searchLabel')}</label>
      <div className="mt-2 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,0.4fr)]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" aria-hidden="true" />
          <input id="npc-directory-search" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('npcDirectory.searchPlaceholder')} className="app-input min-h-11 w-full pl-10" autoComplete="off" />
        </div>
        <div>
          <label htmlFor="npc-location-filter" className="sr-only">{t('npcDirectory.locationFilter')}</label>
          <input id="npc-location-filter" value={locationFilter} onChange={event => setLocationFilter(event.target.value)} placeholder={t('npcDirectory.locationPlaceholder')} className="app-input min-h-11 w-full" autoComplete="off" />
        </div>
      </div>
      <p className="mt-2 text-xs text-content-muted" aria-live="polite">{requestedSearch.length === 1 ? t('npcDirectory.searchMinimum') : resultLabel}</p>
    </section>

    {loading ? <LoadingState className="min-h-72" title={t('npcDirectory.loading')} />
      : failed ? <ErrorState title={t('npcDirectory.error')} description={t('npcDirectory.errorHelp')} action={<button type="button" onClick={() => setReloadKey(value => value + 1)} className="app-button-secondary">{t('common.retry')}</button>} />
        : payload?.items.length ? <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-label={resultLabel}>{payload.items.map(npc => <NpcCard key={npc.canonical_id} npc={npc} />)}</div>
          <PaginationControls className="mt-8" skip={payload.skip} limit={payload.limit} total={payload.total} loading={loading} onPrevious={() => changePage(Math.max(0, payload.skip - payload.limit))} onNext={() => changePage(payload.skip + payload.limit)} />
        </> : <EmptyState icon={<UserRound />} title={t('npcDirectory.empty')} description={t('npcDirectory.emptyHelp')} />}
  </Page>;
}
