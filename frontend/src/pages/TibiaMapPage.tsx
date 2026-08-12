import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BookOpenCheck, Crown, Info, MapPinned, Search, Sparkles, Swords, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { tibiaMapApi, type TibiaMapBootstrap, type TibiaMapLayer, type TibiaMapResult } from '../services/tibiaMap';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));

const layerIcons = { hunt_zone: MapPinned, creature: Swords, boss: Crown, quest: BookOpenCheck, location: Sparkles };
const layers = Object.keys(layerIcons) as TibiaMapLayer[];

export default function TibiaMapPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [bootstrap, setBootstrap] = useState<TibiaMapBootstrap | null>(null);
  const [query, setQuery] = useState(params.get('q') || params.get('name') || params.get('slug')?.split('-').join(' ') || '');
  const [activeLayers, setActiveLayers] = useState<Set<TibiaMapLayer>>(new Set(layers));
  const [results, setResults] = useState<TibiaMapResult[]>([]);
  const [selected, setSelected] = useState<TibiaMapResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    void tibiaMapApi.bootstrap(controller.signal).then((data) => {
      setBootstrap(data);
      if (!query.trim()) setResults(data.hunt_zones);
    }).catch(() => setBootstrap(null)).finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResults(bootstrap?.hunt_zones || []);
      setSelected(null);
      if (!normalized && params.has('q')) {
        const next = new URLSearchParams(params);
        next.delete('q');
        setParams(next, { replace: true });
      }
      return undefined;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      void tibiaMapApi.search(normalized, [...activeLayers], controller.signal).then((data) => {
        setResults(data);
        const requestedType = params.get('entityType');
        const requestedSlug = params.get('slug');
        setSelected(data.find((row) => (!requestedType || row.entity_type === requestedType) && (!requestedSlug || row.slug === requestedSlug)) || data[0] || null);
        if (params.get('q') !== normalized) {
          const next = new URLSearchParams(params);
          next.set('q', normalized);
          setParams(next, { replace: true });
        }
      }).catch(() => setResults([])).finally(() => setLoading(false));
    }, 280);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [activeLayers, bootstrap, params, query, setParams]);

  const visible = useMemo(() => results.filter((row) => activeLayers.has(row.entity_type)), [activeLayers, results]);
  const markerSource = selected ? [selected] : visible;
  const markers = markerSource.filter((row) => row.x != null && row.y != null && !row.bounds).map((row) => ({ x: row.x as number, y: row.y as number, label: row.name }));
  const regions = markerSource.filter((row) => row.bounds).map((row) => ({ minX: row.bounds!.min_x, minY: row.bounds!.min_y, maxX: row.bounds!.max_x, maxY: row.bounds!.max_y, label: row.name }));

  const toggleLayer = (layer: TibiaMapLayer) => setActiveLayers((current) => {
    const next = new Set(current);
    if (next.has(layer)) next.delete(layer); else next.add(layer);
    return next;
  });

  return <div className="relative left-1/2 w-[calc(100vw-1rem)] -translate-x-1/2 py-3 sm:w-[calc(100vw-2rem)]">
    <header className="mb-3 flex flex-wrap items-end justify-between gap-3 rounded-2xl border border-line bg-surface-raised p-4">
      <div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-primary">{t('map.beta')}</p><h1 className="text-2xl font-bold text-content-primary">{t('map.title')}</h1><p className="mt-1 max-w-2xl text-sm text-content-secondary">{t('map.subtitle')}</p></div>
      {bootstrap?.base_map ? <span className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-content-muted">{bootstrap.base_map.source}</span> : null}
    </header>
    <div className="grid min-h-[calc(100vh-12rem)] gap-3 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col rounded-2xl border border-line bg-surface-raised p-3">
        <label className="relative block"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('map.searchPlaceholder')} aria-label={t('map.searchLabel')} className="app-input h-11 w-full pl-10 pr-9" />{query ? <button type="button" onClick={() => setQuery('')} aria-label={t('a11y.clearSearch')} className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center text-content-muted"><X className="size-4" /></button> : null}</label>
        <div className="my-3 flex flex-wrap gap-1.5">{layers.map((layer) => { const Icon = layerIcons[layer]; return <button key={layer} type="button" aria-pressed={activeLayers.has(layer)} onClick={() => toggleLayer(layer)} className={`inline-flex min-h-9 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold ${activeLayers.has(layer) ? 'border-primary/40 bg-primary/10 text-primary' : 'border-line text-content-muted'}`}><Icon className="size-3.5" />{t(`map.layers.${layer}`)}</button>; })}</div>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto" aria-live="polite">
          {loading ? <p className="p-4 text-sm text-content-muted">{t('map.loading')}</p> : null}
          {!loading && !visible.length ? <p className="rounded-xl border border-line bg-surface p-4 text-sm text-content-muted">{t('map.noResults')}</p> : null}
          {visible.map((row) => { const Icon = layerIcons[row.entity_type]; return <button key={row.id} type="button" onClick={() => setSelected(row)} className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition ${selected?.id === row.id ? 'border-primary/50 bg-primary/10' : 'border-line bg-surface hover:bg-surface-active'}`}><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><Icon className="size-4" /></span><span className="min-w-0"><strong className="block truncate text-sm text-content-primary">{row.name}</strong><small className="block truncate text-xs text-content-muted">{row.subtitle || t(`map.layers.${row.entity_type}`)}</small><small className={`mt-1 block text-[10px] ${row.geometry_status === 'mapped' ? 'text-success' : 'text-content-muted'}`}>{row.geometry_status === 'mapped' ? t('map.mapped') : t('map.knowledgeOnly')}</small></span></button>; })}
        </div>
      </aside>
      <section className="relative min-h-[32rem] overflow-hidden rounded-2xl border border-line bg-surface-base">
        {bootstrap?.base_map ? <Suspense fallback={<div className="grid h-full place-items-center text-content-muted">{t('map.loading')}</div>}><TibiaMapViewer imageUrl={bootstrap.base_map.image_url} label={selected?.name || t('map.title')} floor={selected?.z ?? bootstrap.base_map.floor} mapBounds={bootstrap.base_map.bounds} center={selected?.x != null && selected?.y != null ? { x: selected.x, y: selected.y } : undefined} markers={markers} regions={regions} fill emptyMessage={t('map.noBaseMap')} /></Suspense> : <div className="grid h-full place-items-center p-8 text-center text-content-muted"><div><MapPinned className="mx-auto mb-3 size-10 opacity-50" /><p>{t('map.noBaseMap')}</p></div></div>}
        {selected ? <div className="absolute inset-x-3 bottom-3 z-[600] rounded-xl border border-line bg-surface-overlay/95 p-4 shadow-xl backdrop-blur sm:inset-x-auto sm:right-3 sm:w-80"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase text-primary">{t(`map.layers.${selected.entity_type}`)}</p><h2 className="text-lg font-bold text-content-primary">{selected.name}</h2></div><button type="button" onClick={() => setSelected(null)} aria-label={t('map.closeDetails')}><X className="size-4" /></button></div>{selected.geometry_status === 'knowledge_only' ? <p className="mt-2 flex gap-2 text-xs text-content-muted"><Info className="size-4 shrink-0" />{t('map.noGeometry')}</p> : <p className="mt-2 text-xs text-content-secondary">{t('map.coordinates', { x: selected.x ?? '—', y: selected.y ?? '—', z: selected.z ?? '—' })}</p>}<div className="mt-3 flex gap-2"><Link to={selected.to} className="app-button-primary app-button-sm">{t('map.openDetails')}</Link>{selected.entity_type !== 'hunt_zone' && selected.related_hunt_zones?.[0] ? <button type="button" className="app-button-secondary app-button-sm" onClick={() => setSelected(selected.related_hunt_zones![0])}>{t('map.showHuntZone')}</button> : null}</div></div> : null}
      </section>
    </div>
  </div>;
}
