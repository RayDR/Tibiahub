import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BookOpenCheck, ChevronDown, ChevronUp, Crown, Info, MapPinned, PanelLeftClose, PanelLeftOpen, Search, Sparkles, Swords, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { tibiaMapApi, type HuntZoneMapContext, type TibiaMapBootstrap, type TibiaMapLayer, type TibiaMapResult } from '../services/tibiaMap';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));
const layerIcons = { hunt_zone: MapPinned, creature: Swords, boss: Crown, quest: BookOpenCheck, location: Sparkles };
const layers = Object.keys(layerIcons) as TibiaMapLayer[];

export default function TibiaMapPage() {
  const { t } = useTranslation(); const [params, setParams] = useSearchParams();
  const [floor, setFloor] = useState(Number(params.get('floor') || 7));
  const [bootstrap, setBootstrap] = useState<TibiaMapBootstrap | null>(null);
  const [query, setQuery] = useState(params.get('q') || params.get('slug')?.replaceAll('-', ' ') || '');
  const [activeLayers, setActiveLayers] = useState<Set<TibiaMapLayer>>(new Set(layers));
  const [results, setResults] = useState<TibiaMapResult[]>([]); const [selected, setSelected] = useState<TibiaMapResult | null>(null);
  const [context, setContext] = useState<HuntZoneMapContext | null>(null); const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true); const [showPathfinding, setShowPathfinding] = useState(false);

  useEffect(() => { const controller = new AbortController(); setLoading(true); void tibiaMapApi.bootstrap(floor, controller.signal).then(setBootstrap).catch(() => setBootstrap(null)).finally(() => setLoading(false)); return () => controller.abort(); }, [floor]);
  useEffect(() => {
    const normalized = query.trim(); if (normalized.length < 2) { setResults([]); return undefined; }
    const controller = new AbortController(); const timer = window.setTimeout(() => { setLoading(true); void tibiaMapApi.search(normalized, [...activeLayers], controller.signal).then((data) => {
      setResults(data); const requestedType = params.get('entityType'); const requestedSlug = params.get('slug'); const next = data.find((row) => (!requestedType || row.entity_type === requestedType) && (!requestedSlug || row.slug === requestedSlug)) || data[0] || null; selectResult(next, false);
    }).catch(() => setResults([])).finally(() => setLoading(false)); }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  // Params are intentionally read to restore a deep link, not to restart search after our own URL update.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLayers, query]);

  const selectResult = (row: TibiaMapResult | null, updateUrl = true) => {
    setSelected(row); setContext(null);
    if (!row) return;
    if (row.z != null && row.z !== floor) setFloor(row.z);
    if (row.entity_type === 'hunt_zone' && (row.slug || row.entity_id)) void tibiaMapApi.huntZoneContext(row.slug || row.entity_id as number).then(setContext).catch(() => setContext(null));
    if (updateUrl) { const next = new URLSearchParams(); if (query.trim()) next.set('q', query.trim()); next.set('entityType', row.entity_type); if (row.slug) next.set('slug', row.slug); next.set('floor', String(row.z ?? floor)); setParams(next, { replace: true }); }
  };
  const visible = useMemo(() => results.filter((row) => row.entity_type === 'town' || activeLayers.has(row.entity_type as TibiaMapLayer)), [activeLayers, results]);
  const markerRows = context?.markers.length ? context.markers.map((row) => ({ x: row.x, y: row.y, label: row.name, imageUrl: row.image_url })) : selected ? [selected].filter((row) => row.x != null && row.y != null).map((row) => ({ x: row.x as number, y: row.y as number, label: row.name, imageUrl: row.image_url })) : [];
  const regions = selected?.bounds ? [{ minX: selected.bounds.min_x, minY: selected.bounds.min_y, maxX: selected.bounds.max_x, maxY: selected.bounds.max_y, label: selected.name }] : [];
  const map = bootstrap?.world_map;

  return <div className="relative left-1/2 -my-4 h-[calc(100dvh-var(--app-nav-clearance,5rem)-var(--app-mobile-nav-clearance,0rem))] w-screen -translate-x-1/2 overflow-hidden bg-surface-base">
    {map ? <Suspense fallback={<div className="grid h-full place-items-center text-content-muted">{t('map.loading')}</div>}><TibiaMapViewer imageUrl={map.image_url} pathfindingUrl={map.pathfinding_url} showPathfinding={showPathfinding} label={selected?.name || t('map.title')} floor={floor} floorLabel={t('map.floor', { floor })} mapBounds={map.bounds} center={selected?.x != null && selected?.y != null ? { x: selected.x, y: selected.y } : undefined} markers={markerRows} regions={regions} paths={(context?.routes || []).map((route) => ({ id: route.id, label: route.name, points: route.points }))} coordinateMode="world" fill emptyMessage={t('map.noBaseMap')} resetLabel={t('map.reset')} zoomInLabel={t('map.zoomIn')} zoomOutLabel={t('map.zoomOut')} /></Suspense> : <div className="grid h-full place-items-center p-8 text-center text-content-muted"><p>{t('map.noBaseMap')}</p></div>}

    <div className="absolute left-3 top-3 z-[1100] flex max-w-[calc(100%-6rem)] items-center gap-2">
      <button type="button" onClick={() => setSidebarOpen((value) => !value)} className="grid size-11 shrink-0 place-items-center rounded-xl border border-line bg-surface-overlay shadow-lg" aria-label={sidebarOpen ? t('map.collapseSidebar') : t('map.expandSidebar')}>{sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}</button>
      <label className="relative block w-[min(28rem,calc(100vw-8rem))]"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('map.searchPlaceholder')} aria-label={t('map.searchLabel')} className="app-input h-11 w-full bg-surface-overlay pl-10 pr-9 shadow-lg" />{query ? <button type="button" onClick={() => { setQuery(''); setSelected(null); setContext(null); }} aria-label={t('a11y.clearSearch')} className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center"><X className="size-4" /></button> : null}</label>
    </div>

    <div className="absolute right-3 top-40 z-[1100] flex flex-col gap-1 rounded-xl border border-line bg-surface-overlay p-1 shadow-lg">
      <button type="button" disabled={!bootstrap?.available_floors.includes(floor - 1)} onClick={() => setFloor((value) => value - 1)} className="grid size-10 place-items-center disabled:opacity-30" aria-label={t('map.floorUp')}><ChevronUp size={18} /></button><span className="text-center text-xs font-bold">{floor}</span><button type="button" disabled={!bootstrap?.available_floors.includes(floor + 1)} onClick={() => setFloor((value) => value + 1)} className="grid size-10 place-items-center disabled:opacity-30" aria-label={t('map.floorDown')}><ChevronDown size={18} /></button>
    </div>

    {sidebarOpen ? <aside className="absolute bottom-3 left-3 top-16 z-[1050] flex w-[min(22rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-line bg-surface-overlay/95 p-3 shadow-2xl backdrop-blur">
      <div className="mb-3 flex flex-wrap gap-1.5">{layers.map((layer) => { const Icon = layerIcons[layer]; return <button key={layer} type="button" aria-pressed={activeLayers.has(layer)} onClick={() => setActiveLayers((current) => { const next = new Set(current); next.has(layer) ? next.delete(layer) : next.add(layer); return next; })} className={`inline-flex min-h-9 items-center gap-1 rounded-full border px-2 text-xs ${activeLayers.has(layer) ? 'border-primary/40 bg-primary/10 text-primary' : 'border-line text-content-muted'}`}><Icon size={13} />{t(`map.layers.${layer}`)}</button>; })}</div>
      <label className="mb-3 flex items-center gap-2 text-xs text-content-secondary"><input type="checkbox" checked={showPathfinding} onChange={(event) => setShowPathfinding(event.target.checked)} />{t('map.pathfinding')}</label>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto" aria-live="polite">
        {!query.trim() ? <><p className="px-1 text-xs font-bold uppercase tracking-wide text-content-muted">{t('map.knownTowns')}</p>{bootstrap?.towns.map((town) => <button key={town.id} type="button" onClick={() => selectResult(town)} className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left hover:border-primary/40"><MapPinned className="size-4 text-primary" /><strong className="text-sm">{town.name}</strong></button>)}</> : null}
        {loading ? <p className="p-3 text-sm text-content-muted">{t('map.loading')}</p> : null}{!loading && query.trim().length >= 2 && !visible.length ? <p className="p-3 text-sm text-content-muted">{t('map.noResults')}</p> : null}
        {visible.map((row) => { const Icon = row.entity_type === 'town' ? MapPinned : layerIcons[row.entity_type as TibiaMapLayer]; return <button key={row.id} type="button" onClick={() => selectResult(row)} className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left ${selected?.id === row.id ? 'border-primary/50 bg-primary/10' : 'border-line bg-surface'}`}>{row.image_url ? <img src={row.image_url} alt="" className="size-9 object-contain [image-rendering:pixelated]" /> : <Icon className="size-5 text-primary" />}<span className="min-w-0"><strong className="block truncate text-sm">{row.name}</strong><small className="block truncate text-content-muted">{row.subtitle || t(`map.layers.${row.entity_type}`, { defaultValue: t('map.town') })}</small></span></button>; })}
      </div>
      {selected ? <div className="mt-3 border-t border-line pt-3"><h2 className="font-bold">{selected.name}</h2>{selected.geometry_status === 'knowledge_only' ? <p className="mt-1 flex gap-2 text-xs text-content-muted"><Info className="size-4 shrink-0" />{t('map.noGeometry')}</p> : <p className="mt-1 text-xs text-content-muted">{t('map.coordinates', { x: selected.x, y: selected.y, z: selected.z })}</p>}{context?.creatures.length ? <div className="mt-2 flex flex-wrap gap-1">{context.creatures.map((creature) => <Link key={creature.id} to={`/creatures/${creature.slug || creature.id}`} title={`${creature.name} · ${creature.hitpoints} HP · ${creature.experience} EXP`}><img src={creature.image_url} alt={creature.name} className="size-10 rounded border border-line object-contain [image-rendering:pixelated]" /></Link>)}</div> : null}{selected.to ? <Link to={selected.to} className="app-button-primary app-button-sm mt-3">{t('map.openDetails')}</Link> : null}</div> : null}
      {map ? <p className="mt-2 border-t border-line pt-2 text-[10px] text-content-muted">{map.attribution} · {map.upstream_commit.slice(0, 12)}</p> : null}
    </aside> : null}
  </div>;
}
