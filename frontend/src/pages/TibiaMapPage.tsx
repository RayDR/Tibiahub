import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  BookOpenCheck,
  ChevronDown,
  ChevronUp,
  Clock3,
  Crown,
  Info,
  MapPin,
  MapPinned,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sparkles,
  Swords,
  UserRound,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  tibiaMapApi,
  type HuntZoneMapContext,
  type SpatialEvidence,
  type TibiaMapBootstrap,
  type TibiaMapLayer,
  type TibiaMapResult,
} from '../services/tibiaMap';
import { formatDisplayFloor } from '../utils/tibiaFloors';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));
const layerIcons = {
  hunt_zone: MapPinned,
  creature: Swords,
  boss: Crown,
  item: Package,
  quest: BookOpenCheck,
  npc: UserRound,
  location: Sparkles,
};
const layers = Object.keys(layerIcons) as TibiaMapLayer[];
const RECENT_MAP_TARGETS_KEY = 'tibiahub_map_recent_targets';

interface RecentMapTarget {
  id: string;
  entityType: TibiaMapResult['entity_type'];
  name: string;
  slug?: string | null;
}

function initialFloor(value: string | null) {
  const floor = Number(value ?? 7);
  return Number.isInteger(floor) && floor >= 0 && floor <= 15 ? floor : 7;
}

function loadRecentTargets(): RecentMapTarget[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECENT_MAP_TARGETS_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.slice(0, 6) : [];
  } catch {
    return [];
  }
}

function saveRecentTarget(row: TibiaMapResult, current: RecentMapTarget[]): RecentMapTarget[] {
  const target = { id: row.id, entityType: row.entity_type, name: row.name, slug: row.slug };
  const next = [target, ...current.filter((entry) => entry.id !== target.id)].slice(0, 6);
  try {
    localStorage.setItem(RECENT_MAP_TARGETS_KEY, JSON.stringify(next));
  } catch {
    // The map remains fully usable when browser storage is unavailable.
  }
  return next;
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
  const [recentTargets, setRecentTargets] = useState<RecentMapTarget[]>(loadRecentTargets);
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

  const selectResult = (row: TibiaMapResult | null, updateUrl = true, remember = true, preferredLocation?: string | null) => {
    setSelected(row);
    const evidence = row?.spatial_evidence?.find((item) => item.label === preferredLocation)
      || row?.spatial_evidence?.[0]
      || (row?.x != null && row.y != null
        ? { x: row.x, y: row.y, z: row.z, bounds: row.bounds, label: row.name }
        : null);
    setFocusedEvidence(evidence);
    if (evidence?.z != null && evidence.z !== floor) setFloor(evidence.z);
    if (!row) setContext(null);
    if (row && remember) setRecentTargets((current) => saveRecentTarget(row, current));
    if (updateUrl) {
      const next = new URLSearchParams();
      if (query.trim()) next.set('q', query.trim());
      if (row) {
        next.set('entityType', row.entity_type);
        if (row.slug) next.set('slug', row.slug);
      }
      next.set('floor', String(evidence?.z ?? floor));
      setParams(next, { replace: true });
    }
  };

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResults([]);
      setSearchLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    let current = true;
    const timer = window.setTimeout(() => {
      setSearchLoading(true);
      void tibiaMapApi.search(normalized, [...activeLayers], controller.signal)
        .then((data) => {
          if (!current) return;
          const townMatches = (bootstrap?.towns || []).filter((town) => town.name.toLocaleLowerCase().includes(normalized.toLocaleLowerCase()));
          const combined = [...townMatches, ...data];
          setResults(combined);
          const requestedType = params.get('entityType');
          const requestedSlug = params.get('slug');
          const next = combined.find((row) => (
            (!requestedType || row.entity_type === requestedType)
            && (!requestedSlug || row.slug === requestedSlug)
          )) || combined[0] || null;
          selectResult(next, false, false, params.get('location'));
        })
        .catch(() => { if (current && !controller.signal.aborted) setResults([]); })
        .finally(() => { if (current) setSearchLoading(false); });
    }, 250);
    return () => { current = false; window.clearTimeout(timer); controller.abort(); };
  // URL params only restore the initial deep link; selection updates must not restart search.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLayers, bootstrap?.towns, query]);

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

  const visible = useMemo(
    () => results.filter((row) => row.entity_type === 'town' || activeLayers.has(row.entity_type as TibiaMapLayer)),
    [activeLayers, results],
  );
  const selectedEvidence = selected?.spatial_evidence || [];
  const entityMarkers = useMemo(() => {
    if (context?.markers.length) {
      return context.markers
        .filter((row) => row.z == null || row.z === floor)
        .map((row) => ({ x: row.x, y: row.y, label: row.name, imageUrl: row.image_url }));
    }
    return selectedEvidence
      .filter((row) => row.z == null || row.z === floor)
      .map((row) => ({ x: row.x, y: row.y, label: row.label || selected?.name || '', subtitle: row.relationship || undefined }));
  }, [context, floor, selected?.name, selectedEvidence]);
  const mapMarkers = useMemo(() => [
    ...entityMarkers,
    ...(bootstrap?.towns || [])
      .filter((town) => town.z == null || town.z === floor)
      .map((town) => ({ x: town.x as number, y: town.y as number, label: town.name, kind: 'town' as const })),
  ], [bootstrap?.towns, entityMarkers, floor]);
  const focus = focusedEvidence && (focusedEvidence.z == null || focusedEvidence.z === floor) ? focusedEvidence : null;
  const regions = focus?.bounds ? [{
    minX: focus.bounds.min_x,
    minY: focus.bounds.min_y,
    maxX: focus.bounds.max_x,
    maxY: focus.bounds.max_y,
    label: focus.label || selected?.name || '',
  }] : [];
  const map = bootstrap?.world_map;

  const toggleLayer = (layer: TibiaMapLayer) => {
    setActiveLayers((current) => {
      if (current.size === 1 && current.has(layer)) return new Set(layers);
      return new Set([layer]);
    });
    setSidebarOpen(true);
  };

  const openRecent = (target: RecentMapTarget) => {
    if (target.entityType === 'town') {
      const town = bootstrap?.towns.find((row) => row.id === target.id);
      if (town) selectResult(town);
      return;
    }
    const next = new URLSearchParams({ q: target.name, entityType: target.entityType, floor: String(floor) });
    if (target.slug) next.set('slug', target.slug);
    setParams(next, { replace: true });
    setQuery(target.name);
    setSidebarOpen(true);
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    selectResult(null);
  };

  const renderResult = (row: TibiaMapResult) => {
    const Icon = row.entity_type === 'town' ? MapPinned : layerIcons[row.entity_type as TibiaMapLayer];
    return <button
      key={row.id}
      type="button"
      onClick={() => selectResult(row)}
      className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition-colors ${selected?.id === row.id ? 'border-primary/50 bg-primary/10' : 'border-line bg-surface hover:border-primary/40 hover:bg-surface-hover'}`}
    >
      {row.image_url
        ? <img src={row.image_url} alt="" className="size-9 object-contain [image-rendering:pixelated]" />
        : <Icon className="size-5 shrink-0 text-primary" />}
      <span className="min-w-0 flex-1">
        <strong className="block truncate text-sm">{row.name}</strong>
        <small className="block truncate text-content-muted">
          {row.geometry_status === 'mapped' && row.location_labels?.length
            ? row.location_labels.join(' · ')
            : row.subtitle || t(`map.layers.${row.entity_type}`, { defaultValue: t('map.town') })}
        </small>
      </span>
      {row.geometry_status === 'knowledge_only' ? <MapPin className="size-4 shrink-0 text-content-muted" /> : null}
    </button>;
  };

  const floorControl = <div className="overflow-hidden rounded-xl border border-line bg-surface-overlay shadow-lg backdrop-blur">
    <button
      type="button"
      disabled={!bootstrap?.available_floors.includes(floor - 1)}
      onClick={() => setFloor((value) => value - 1)}
      className="grid size-10 place-items-center border-b border-line hover:bg-surface-hover disabled:opacity-30"
      aria-label={t('map.floorUp')}
    ><ChevronUp size={18} /></button>
    <span className="grid min-h-9 min-w-10 place-items-center border-b border-line px-1 text-xs font-bold" title={t('map.internalFloor', { floor })}>{formatDisplayFloor(floor)}</span>
    <button
      type="button"
      disabled={!bootstrap?.available_floors.includes(floor + 1)}
      onClick={() => setFloor((value) => value + 1)}
      className="grid size-10 place-items-center hover:bg-surface-hover disabled:opacity-30"
      aria-label={t('map.floorDown')}
    ><ChevronDown size={18} /></button>
  </div>;

  return <div className="relative h-[calc(100dvh-var(--app-nav-clearance)-var(--app-mobile-nav-clearance))] min-h-0 w-full overflow-hidden bg-surface-base" aria-label={t('map.workspace')}>
    {map ? <Suspense fallback={<div className="grid h-full place-items-center text-content-muted">{t('map.loading')}</div>}>
      <TibiaMapViewer
        imageUrl={map.image_url}
        pathfindingUrl={map.pathfinding_url}
        showPathfinding={showPathfinding}
        label={selected?.name || t('map.title')}
        floor={floor}
        floorLabel={t('map.floor', { floor: formatDisplayFloor(floor) })}
        mapBounds={map.bounds}
        center={focus ? { x: focus.x, y: focus.y } : undefined}
        markers={mapMarkers}
        regions={regions}
        paths={(context?.routes || []).map((route) => ({ id: route.id, label: route.name, points: route.points }))}
        coordinateMode="world"
        fill
        showFloorBadge={false}
        controlFooter={floorControl}
        emptyMessage={t('map.noBaseMap')}
        resetLabel={t('map.reset')}
        zoomInLabel={t('map.zoomIn')}
        zoomOutLabel={t('map.zoomOut')}
      />
    </Suspense> : <div className="grid h-full place-items-center p-8 text-center text-content-muted"><p>{mapLoading ? t('map.loading') : t('map.noBaseMap')}</p></div>}

    <div className="pointer-events-none absolute inset-x-3 top-3 z-map-overlay flex min-w-0 flex-col gap-2 lg:right-16 lg:flex-row">
      <div className="pointer-events-auto flex w-full min-w-0 gap-2 lg:w-[23rem] lg:shrink-0">
        <button
          type="button"
          onClick={() => setSidebarOpen((value) => !value)}
          className="grid size-11 shrink-0 place-items-center rounded-xl border border-line bg-surface-overlay shadow-lg backdrop-blur"
          aria-label={sidebarOpen ? t('map.collapseSidebar') : t('map.expandSidebar')}
          aria-expanded={sidebarOpen}
        >{sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}</button>
        <label className="relative block min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
          <input
            value={query}
            onChange={(event) => { setQuery(event.target.value); if (event.target.value.trim()) setSidebarOpen(true); }}
            placeholder={t('map.searchPlaceholder')}
            aria-label={t('map.searchLabel')}
            className="app-input h-11 w-full bg-surface-overlay pl-10 pr-9 shadow-lg backdrop-blur"
          />
          {query ? <button type="button" onClick={clearSearch} aria-label={t('a11y.clearSearch')} className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-lg hover:bg-surface-hover"><X className="size-4" /></button> : null}
        </label>
      </div>

      <div className="pointer-events-auto flex min-w-0 flex-1 gap-1.5 overflow-x-auto rounded-xl bg-surface-overlay/90 p-1.5 shadow-lg backdrop-blur [scrollbar-width:none]" aria-label={t('map.filters')}>
        {layers.map((layer) => {
          const Icon = layerIcons[layer];
          return <button
            key={layer}
            type="button"
            aria-pressed={activeLayers.size === 1 && activeLayers.has(layer)}
            onClick={() => toggleLayer(layer)}
            className={`inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors ${activeLayers.size === 1 && activeLayers.has(layer) ? 'border-primary/40 bg-primary/10 text-primary' : 'border-line bg-surface text-content-muted hover:text-content-primary'}`}
          ><Icon size={13} />{t(`map.layers.${layer}`)}</button>;
        })}
      </div>
    </div>

    {sidebarOpen ? <aside className="absolute bottom-3 left-3 right-3 z-map-overlay flex max-h-[52%] flex-col overflow-hidden rounded-2xl border border-line bg-surface-overlay/95 p-3 shadow-2xl backdrop-blur lg:bottom-3 lg:right-auto lg:top-16 lg:max-h-none lg:w-[23rem]" aria-label={t('map.sidebar')}>
      <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-content-muted/30 lg:hidden" aria-hidden="true" />
      <div className="mb-2 flex items-center justify-between gap-2 border-b border-line pb-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-bold uppercase tracking-wide text-content-muted">{query.trim() ? t('map.searchResults') : t('map.localNavigation')}</p>
          {query.trim() ? <p className="truncate text-xs text-content-secondary">{query.trim()}</p> : null}
        </div>
        <label className="flex shrink-0 items-center gap-1.5 text-xs text-content-secondary"><input type="checkbox" checked={showPathfinding} onChange={(event) => setShowPathfinding(event.target.checked)} />{t('map.pathfinding')}</label>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain pr-0.5" aria-live="polite">
        {!query.trim() && recentTargets.length ? <section>
          <h2 className="mb-1.5 flex items-center gap-1.5 px-1 text-xs font-bold uppercase tracking-wide text-content-muted"><Clock3 size={13} />{t('map.recent')}</h2>
          <div className="space-y-1.5">{recentTargets.map((target) => <button key={target.id} type="button" onClick={() => openRecent(target)} className="flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm text-content-secondary hover:bg-surface-hover hover:text-content-primary"><Clock3 className="size-4 shrink-0" /><span className="truncate">{target.name}</span></button>)}</div>
        </section> : null}
        {!query.trim() ? <section className={recentTargets.length ? 'border-t border-line pt-3' : ''}>
          <h2 className="mb-1.5 px-1 text-xs font-bold uppercase tracking-wide text-content-muted">{t('map.knownTowns')}</h2>
          <div className="space-y-1.5">{bootstrap?.towns.map((town) => renderResult(town))}</div>
        </section> : null}
        {searchLoading ? <p className="p-3 text-sm text-content-muted">{t('map.loading')}</p> : null}
        {!searchLoading && query.trim().length >= 2 && !visible.length ? <p className="p-3 text-sm text-content-muted">{t('map.noResults')}</p> : null}
        {!searchLoading && query.trim().length >= 2 ? visible.map(renderResult) : null}
      </div>

      {selected ? <div className="mt-3 border-t border-line pt-3">
        <h2 className="font-bold">{selected.name}</h2>
        {selected.geometry_status === 'knowledge_only'
          ? <p className="mt-1 flex gap-2 text-xs text-content-muted"><Info className="size-4 shrink-0" />{t('map.locationNotMapped')}</p>
          : <p className="mt-1 text-xs text-content-muted">{t('map.coordinates', { x: focus?.x, y: focus?.y, z: focus?.z != null ? formatDisplayFloor(focus.z) : t('common.unknown') })}</p>}
        {selectedEvidence.length > 1 ? <div className="mt-2 flex flex-wrap gap-1">{selectedEvidence.map((value, index) => <button key={`${value.x}:${value.y}:${value.z}:${index}`} type="button" onClick={() => { setFocusedEvidence(value); if (value.z != null) setFloor(value.z); }} className={`rounded-full border px-2 py-1 text-[11px] ${focusedEvidence === value ? 'border-primary bg-primary/10 text-primary' : 'border-line'}`}>{value.label || t('map.mappedLocation', { index: index + 1 })}</button>)}</div> : null}
        {context?.creatures.length ? <div className="mt-2 flex flex-wrap gap-1">{context.creatures.map((creature) => <Link key={creature.id} to={`/creatures/${creature.slug || creature.id}`} title={`${creature.name} · ${creature.hitpoints ?? t('common.unknown')} HP · ${creature.experience ?? t('common.unknown')} EXP`}><img src={creature.image_url} alt={creature.name} className="size-10 rounded border border-line object-contain [image-rendering:pixelated]" /></Link>)}</div> : null}
        {selected.to ? <Link to={selected.to} className="app-button-primary app-button-sm mt-3">{t('map.openDetails')}</Link> : null}
      </div> : null}
      {map ? <p className="mt-2 border-t border-line pt-2 text-[10px] text-content-muted">{map.attribution} · {map.upstream_commit.slice(0, 12)}</p> : null}
    </aside> : null}
  </div>;
}
