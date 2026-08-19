import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BookOpenCheck, ChevronDown, ChevronUp, Crown, Info, MapPin, MapPinned, Package, PanelLeftClose, PanelLeftOpen, Search, Sparkles, Swords, UserRound, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { tibiaMapApi, type HuntZoneMapContext, type SpatialEvidence, type TibiaMapBootstrap, type TibiaMapLayer, type TibiaMapResult } from '../services/tibiaMap';
import { formatDisplayFloor } from '../utils/tibiaFloors';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));
const layerIcons = { hunt_zone: MapPinned, creature: Swords, boss: Crown, item: Package, quest: BookOpenCheck, npc: UserRound, location: Sparkles };
const layers = Object.keys(layerIcons) as TibiaMapLayer[];

function initialFloor(value: string | null) {
  const floor = Number(value ?? 7);
  return Number.isInteger(floor) && floor >= 0 && floor <= 15 ? floor : 7;
}

export default function TibiaMapPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [floor, setFloor] = useState(() => initialFloor(params.get('floor')));
  const [bootstrap, setBootstrap] = useState<TibiaMapBootstrap | null>(null);
  const [query, setQuery] = useState(params.get('q') || params.get('slug')?.replaceAll('-', ' ') || '');
  const [activeLayers, setActiveLayers] = useState<Set<TibiaMapLayer>>(new Set(layers));
  const [results, setResults] = useState<TibiaMapResult[]>([]);
  const [selected, setSelected] = useState<TibiaMapResult | null>(null);
  const [focusedEvidence, setFocusedEvidence] = useState<SpatialEvidence | null>(null);
  const [context, setContext] = useState<HuntZoneMapContext | null>(null);
  const [mapLoading, setMapLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showPathfinding, setShowPathfinding] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setMapLoading(true);
    void tibiaMapApi.bootstrap(floor, controller.signal)
      .then((value) => { if (current) setBootstrap(value); })
      .catch(() => { if (current && !controller.signal.aborted) setBootstrap(null); })
      .finally(() => { if (current) setMapLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [floor]);

  const selectResult = (row: TibiaMapResult | null, updateUrl = true) => {
    setSelected(row);
    const evidence = row?.spatial_evidence?.[0] || (row?.x != null && row.y != null ? { x: row.x, y: row.y, z: row.z, bounds: row.bounds, label: row.name } : null);
    setFocusedEvidence(evidence);
    if (evidence?.z != null && evidence.z !== floor) setFloor(evidence.z);
    if (!row) setContext(null);
    if (row && updateUrl) {
      const next = new URLSearchParams();
      if (query.trim()) next.set('q', query.trim());
      next.set('entityType', row.entity_type);
      if (row.slug) next.set('slug', row.slug);
      next.set('floor', String(evidence?.z ?? floor));
      setParams(next, { replace: true });
    }
  };

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) { setResults([]); setSearchLoading(false); return undefined; }
    const controller = new AbortController();
    let current = true;
    const timer = window.setTimeout(() => {
      setSearchLoading(true);
      void tibiaMapApi.search(normalized, [...activeLayers], controller.signal)
        .then((data) => {
          if (!current) return;
          setResults(data);
          const requestedType = params.get('entityType');
          const requestedSlug = params.get('slug');
          const next = data.find((row) => (!requestedType || row.entity_type === requestedType) && (!requestedSlug || row.slug === requestedSlug)) || data[0] || null;
          selectResult(next, false);
        })
        .catch(() => { if (current && !controller.signal.aborted) setResults([]); })
        .finally(() => { if (current) setSearchLoading(false); });
    }, 250);
    return () => { current = false; window.clearTimeout(timer); controller.abort(); };
  // URL params only restore the initial deep link; selection updates must not restart search.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLayers, query]);

  useEffect(() => {
    setContext(null);
    if (selected?.entity_type !== 'hunt_zone' || (!selected.slug && selected.entity_id == null)) return undefined;
    const controller = new AbortController();
    let current = true;
    void tibiaMapApi.huntZoneContext(selected.slug || selected.entity_id as number, controller.signal)
      .then((value) => { if (current) setContext(value); })
      .catch(() => { if (current && !controller.signal.aborted) setContext(null); });
    return () => { current = false; controller.abort(); };
  }, [selected]);

  const visible = useMemo(() => results.filter((row) => row.entity_type === 'town' || activeLayers.has(row.entity_type as TibiaMapLayer)), [activeLayers, results]);
  const selectedEvidence = selected?.spatial_evidence || [];
  const markerRows = useMemo(() => {
    if (context?.markers.length) return context.markers.filter((row) => row.z == null || row.z === floor).map((row) => ({ x: row.x, y: row.y, label: row.name, imageUrl: row.image_url }));
    return selectedEvidence.filter((row) => row.z == null || row.z === floor).map((row) => ({ x: row.x, y: row.y, label: row.label || selected?.name || '', subtitle: row.relationship || undefined }));
  }, [context, floor, selected?.name, selectedEvidence]);
  const focus = focusedEvidence && (focusedEvidence.z == null || focusedEvidence.z === floor) ? focusedEvidence : null;
  const regions = focus?.bounds ? [{ minX: focus.bounds.min_x, minY: focus.bounds.min_y, maxX: focus.bounds.max_x, maxY: focus.bounds.max_y, label: focus.label || selected?.name || '' }] : [];
  const map = bootstrap?.world_map;

  return <div className="relative left-1/2 -my-4 h-[calc(100dvh-var(--app-nav-clearance,5rem)-var(--app-mobile-nav-clearance,0rem))] w-screen -translate-x-1/2 overflow-hidden bg-surface-base">
    {map ? <Suspense fallback={<div className="grid h-full place-items-center text-content-muted">{t('map.loading')}</div>}><TibiaMapViewer imageUrl={map.image_url} pathfindingUrl={map.pathfinding_url} showPathfinding={showPathfinding} label={selected?.name || t('map.title')} floor={floor} floorLabel={t('map.floor', { floor: formatDisplayFloor(floor) })} mapBounds={map.bounds} center={focus ? { x: focus.x, y: focus.y } : undefined} markers={markerRows} regions={regions} paths={(context?.routes || []).map((route) => ({ id: route.id, label: route.name, points: route.points }))} coordinateMode="world" fill emptyMessage={t('map.noBaseMap')} resetLabel={t('map.reset')} zoomInLabel={t('map.zoomIn')} zoomOutLabel={t('map.zoomOut')} /></Suspense> : <div className="grid h-full place-items-center p-8 text-center text-content-muted"><p>{mapLoading ? t('map.loading') : t('map.noBaseMap')}</p></div>}

    <div className="absolute left-3 top-3 z-[1100] flex max-w-[calc(100%-6rem)] items-center gap-2">
      <button type="button" onClick={() => setSidebarOpen((value) => !value)} className="grid size-11 shrink-0 place-items-center rounded-xl border border-line bg-surface-overlay shadow-lg" aria-label={sidebarOpen ? t('map.collapseSidebar') : t('map.expandSidebar')}>{sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}</button>
      <label className="relative block w-[min(32rem,calc(100vw-8rem))]"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('map.searchPlaceholder')} aria-label={t('map.searchLabel')} className="app-input h-11 w-full bg-surface-overlay pl-10 pr-9 shadow-lg backdrop-blur" />{query ? <button type="button" onClick={() => { setQuery(''); selectResult(null); }} aria-label={t('a11y.clearSearch')} className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center"><X className="size-4" /></button> : null}</label>
    </div>

    <div className="absolute right-3 top-40 z-[1100] flex flex-col gap-1 rounded-xl border border-line bg-surface-overlay p-1 shadow-lg backdrop-blur">
      <button type="button" disabled={!bootstrap?.available_floors.includes(floor - 1)} onClick={() => setFloor((value) => value - 1)} className="grid size-10 place-items-center disabled:opacity-30" aria-label={t('map.floorUp')}><ChevronUp size={18} /></button>
      <span className="min-w-10 text-center text-xs font-bold" title={t('map.internalFloor', { floor })}>{formatDisplayFloor(floor)}</span>
      <button type="button" disabled={!bootstrap?.available_floors.includes(floor + 1)} onClick={() => setFloor((value) => value + 1)} className="grid size-10 place-items-center disabled:opacity-30" aria-label={t('map.floorDown')}><ChevronDown size={18} /></button>
    </div>

    {sidebarOpen ? <aside className="absolute bottom-3 left-3 top-16 z-[1050] flex w-[min(22rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-line bg-surface-overlay/95 p-3 shadow-2xl backdrop-blur">
      <div className="mb-2 flex flex-wrap gap-1.5">{layers.map((layer) => { const Icon = layerIcons[layer]; return <button key={layer} type="button" aria-pressed={activeLayers.has(layer)} onClick={() => setActiveLayers((current) => { const next = new Set(current); next.has(layer) ? next.delete(layer) : next.add(layer); return next; })} className={`inline-flex min-h-8 items-center gap-1 rounded-full border px-2 text-[11px] ${activeLayers.has(layer) ? 'border-primary/40 bg-primary/10 text-primary' : 'border-line text-content-muted'}`}><Icon size={12} />{t(`map.layers.${layer}`)}</button>; })}</div>
      <label className="mb-2 flex items-center gap-2 border-b border-line pb-2 text-xs text-content-secondary"><input type="checkbox" checked={showPathfinding} onChange={(event) => setShowPathfinding(event.target.checked)} />{t('map.pathfinding')}</label>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto" aria-live="polite">
        {!query.trim() ? <><p className="px-1 text-xs font-bold uppercase tracking-wide text-content-muted">{t('map.knownTowns')}</p>{bootstrap?.towns.map((town) => <button key={town.id} type="button" onClick={() => selectResult(town)} className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left hover:border-primary/40"><MapPinned className="size-4 text-primary" /><strong className="text-sm">{town.name}</strong></button>)}</> : null}
        {searchLoading ? <p className="p-3 text-sm text-content-muted">{t('map.loading')}</p> : null}
        {!searchLoading && query.trim().length >= 2 && !visible.length ? <p className="p-3 text-sm text-content-muted">{t('map.noResults')}</p> : null}
        {visible.map((row) => { const Icon = row.entity_type === 'town' ? MapPinned : layerIcons[row.entity_type as TibiaMapLayer]; return <button key={row.id} type="button" onClick={() => selectResult(row)} className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left ${selected?.id === row.id ? 'border-primary/50 bg-primary/10' : 'border-line bg-surface'}`}>{row.image_url ? <img src={row.image_url} alt="" className="size-9 object-contain [image-rendering:pixelated]" /> : <Icon className="size-5 text-primary" />}<span className="min-w-0"><strong className="block truncate text-sm">{row.name}</strong><small className="block truncate text-content-muted">{row.geometry_status === 'mapped' && row.location_labels?.length ? row.location_labels.join(' · ') : row.subtitle || t(`map.layers.${row.entity_type}`, { defaultValue: t('map.town') })}</small></span>{row.geometry_status === 'knowledge_only' ? <MapPin className="ml-auto size-4 shrink-0 text-content-muted" /> : null}</button>; })}
      </div>
      {selected ? <div className="mt-3 border-t border-line pt-3"><h2 className="font-bold">{selected.name}</h2>{selected.geometry_status === 'knowledge_only' ? <p className="mt-1 flex gap-2 text-xs text-content-muted"><Info className="size-4 shrink-0" />{t('map.locationNotMapped')}</p> : <p className="mt-1 text-xs text-content-muted">{t('map.coordinates', { x: focus?.x, y: focus?.y, z: focus?.z != null ? formatDisplayFloor(focus.z) : t('common.unknown') })}</p>}{selectedEvidence.length > 1 ? <div className="mt-2 flex flex-wrap gap-1">{selectedEvidence.map((value, index) => <button key={`${value.x}:${value.y}:${value.z}:${index}`} type="button" onClick={() => { setFocusedEvidence(value); if (value.z != null) setFloor(value.z); }} className={`rounded-full border px-2 py-1 text-[11px] ${focusedEvidence === value ? 'border-primary bg-primary/10 text-primary' : 'border-line'}`}>{value.label || t('map.mappedLocation', { index: index + 1 })}</button>)}</div> : null}{context?.creatures.length ? <div className="mt-2 flex flex-wrap gap-1">{context.creatures.map((creature) => <Link key={creature.id} to={`/creatures/${creature.slug || creature.id}`} title={`${creature.name} · ${creature.hitpoints ?? t('common.unknown')} HP · ${creature.experience ?? t('common.unknown')} EXP`}><img src={creature.image_url} alt={creature.name} className="size-10 rounded border border-line object-contain [image-rendering:pixelated]" /></Link>)}</div> : null}{selected.to ? <Link to={selected.to} className="app-button-primary app-button-sm mt-3">{t('map.openDetails')}</Link> : null}</div> : null}
      {map ? <p className="mt-2 border-t border-line pt-2 text-[10px] text-content-muted">{map.attribution} · {map.upstream_commit.slice(0, 12)}</p> : null}
    </aside> : null}
  </div>;
}
