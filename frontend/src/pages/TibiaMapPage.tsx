import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  BookOpenCheck,
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Compass,
  Copy,
  Crown,
  Info,
  Layers3,
  MapPin,
  MapPinned,
  Package,
  PanelLeftOpen,
  Route,
  Search,
  Sparkles,
  Swords,
  UserRound,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { TIBIAHUB_TITLE_ICONS } from '../assets/brand/brandTitleIcons';
import {
  tibiaMapApi,
  type HuntZoneMapContext,
  type SpatialEvidence,
  type TibiaMapBootstrap,
  type TibiaMapLayer,
  type TibiaMapResult,
  type TibiaMapViewport,
} from '../services/tibiaMap';
import { formatDisplayFloor } from '../utils/tibiaFloors';
import {
  markersForMapMode,
  requestedMapSelection,
  resolveMapSearchSelection,
} from '../utils/tibiaMapSelection';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));

const layerIcons = {
  hunt_zone: MapPinned,
  creature: Swords,
  boss: Crown,
  quest: BookOpenCheck,
  npc: UserRound,
  location: Sparkles,
};
const layers = Object.keys(layerIcons) as TibiaMapLayer[];
const resultIcons = { ...layerIcons, item: Package, town: MapPin };
const RECENT_MAP_TARGETS_KEY = 'tibiahub_map_recent_targets';

type SidebarTab = 'layers' | 'legend';
type NearbyTab = 'hunt_zone' | 'npc' | 'quest' | 'other';

interface RecentMapTarget {
  id: string;
  canonicalEntityId?: string | null;
  entityType: TibiaMapResult['entity_type'];
  name: string;
  slug?: string | null;
}

interface NearbyResult {
  row: TibiaMapResult;
  distance: number;
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
  const target = {
    id: row.id,
    canonicalEntityId: row.canonical_entity_id,
    entityType: row.entity_type,
    name: row.name,
    slug: row.slug,
  };
  const next = [target, ...current.filter((entry) => entry.id !== target.id)].slice(0, 6);
  try {
    localStorage.setItem(RECENT_MAP_TARGETS_KEY, JSON.stringify(next));
  } catch {
    // Recent targets are a convenience only; map exploration remains functional.
  }
  return next;
}

function previewString(row: TibiaMapResult | null, keys: string[]): string | null {
  if (!row?.preview) return null;
  for (const key of keys) {
    const value = row.preview[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function previewMetric(row: TibiaMapResult | null, keys: string[]): string | null {
  if (!row?.preview) return null;
  for (const key of keys) {
    const value = row.preview[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value.toLocaleString();
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

export default function TibiaMapPage() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [floor, setFloor] = useState(() => initialFloor(params.get('floor')));
  const [bootstrap, setBootstrap] = useState<TibiaMapBootstrap | null>(null);
  const [query, setQuery] = useState(params.get('q') || params.get('slug')?.replace(/-/g, ' ') || '');
  const [activeLayers, setActiveLayers] = useState<Set<TibiaMapLayer>>(new Set(layers));
  const [layerResults, setLayerResults] = useState<Partial<Record<TibiaMapLayer, TibiaMapResult[]>>>({});
  const [layerStates, setLayerStates] = useState<Partial<Record<TibiaMapLayer, 'loading' | 'ready' | 'error'>>>({});
  const [results, setResults] = useState<TibiaMapResult[]>([]);
  const [selected, setSelected] = useState<TibiaMapResult | null>(null);
  const [focusedEvidence, setFocusedEvidence] = useState<SpatialEvidence | null>(null);
  const [context, setContext] = useState<HuntZoneMapContext | null>(null);
  const [recentTargets, setRecentTargets] = useState<RecentMapTarget[]>(loadRecentTargets);
  const [mapLoading, setMapLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches,
  );
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('layers');
  const [nearbyTab, setNearbyTab] = useState<NearbyTab>('hunt_zone');
  const [showRoutes, setShowRoutes] = useState(true);
  const [viewport, setViewport] = useState<TibiaMapViewport | null>(null);
  const viewportRequestSequence = useRef(0);
  const internalParamsUpdate = useRef<string | null>(null);
  const [navigationRequestKey, setNavigationRequestKey] = useState(() => params.toString());
  const requestedSelection = useMemo(() => requestedMapSelection(params), [params]);
  const [searchRequestedSelection, setSearchRequestedSelection] = useState(() => requestedMapSelection(params));
  const isSpanish = i18n.resolvedLanguage?.startsWith('es');

  const copy = useMemo(() => isSpanish ? {
    subtitle: 'Explora el mundo de Tibia. Descubre ubicaciones, planea tus hunts y encuentra tu próxima aventura.',
    motto: 'EL CONOCIMIENTO\nIMPULSA GRANDES\nAVENTURAS',
    layers: 'Capas', legend: 'Leyenda', mapLayers: 'Capas del mapa', filters: 'Filtros', quickFilters: 'Filtros rápidos',
    reset: 'Restablecer', routes: 'Rutas', recent: 'Recientes', allLayers: 'Mostrar todo', huntsOnly: 'Hunts', questsOnly: 'Quests', towns: 'Lugares',
    mapSearch: 'Buscar en el mapa…', coordinates: 'Coordenadas', copyCoordinates: 'Copiar coordenadas', copied: 'Coordenadas copiadas',
    openDetails: 'Abrir detalles', nearby: 'Cerca de aquí', noNearby: 'No hay resultados cercanos en la vista cargada.',
    selectedHint: 'Selecciona un marcador o busca una entidad para ver su información.',
    knowledge: 'Datos documentados', creatures: 'Criaturas', details: 'Detalles', floor: 'Piso', mapData: 'Datos del mapa',
    huntZones: 'Hunts', npcs: 'NPCs', quests: 'Quests', other: 'POIs', distance: 'casillas',
    location: 'Ubicación', loading: 'Cargando capa…', unavailable: 'Sin datos documentados',
  } : {
    subtitle: "Explore Tibia's world. Discover locations, plan your hunts, and find your next adventure.",
    motto: 'KNOWLEDGE\nFUELS GREATER\nADVENTURES',
    layers: 'Layers', legend: 'Legend', mapLayers: 'Map Layers', filters: 'Filters', quickFilters: 'Quick Filters',
    reset: 'Reset', routes: 'Routes', recent: 'Recent', allLayers: 'Show all', huntsOnly: 'Hunts', questsOnly: 'Quests', towns: 'Places',
    mapSearch: 'Search the map…', coordinates: 'Coordinates', copyCoordinates: 'Copy Coordinates', copied: 'Coordinates copied',
    openDetails: 'Open details', nearby: 'Nearby', noNearby: 'No nearby results in the currently loaded view.',
    selectedHint: 'Select a marker or search for an entity to inspect it.',
    knowledge: 'Documented data', creatures: 'Creatures', details: 'Details', floor: 'Floor', mapData: 'Map data',
    huntZones: 'Hunts', npcs: 'NPCs', quests: 'Quests', other: 'POIs', distance: 'tiles',
    location: 'Location', loading: 'Loading layer…', unavailable: 'No documented data',
  }, [isSpanish]);

  const noResultsLabel = isSpanish ? 'No se encontraron resultados.' : 'No results found.';

  const replaceParams = (next: URLSearchParams) => {
    internalParamsUpdate.current = next.toString();
    setParams(next, { replace: true });
  };

  const clearSelectionState = () => {
    setSelected(null);
    setFocusedEvidence(null);
    setContext(null);
  };

  useEffect(() => {
    const serialized = params.toString();
    if (internalParamsUpdate.current === serialized) {
      internalParamsUpdate.current = null;
      return;
    }
    setQuery(params.get('q') || params.get('slug')?.replace(/-/g, ' ') || '');
    setFloor(initialFloor(params.get('floor')));
    setResults([]);
    setSearchError(false);
    clearSelectionState();
    setSearchRequestedSelection(requestedMapSelection(params));
    setNavigationRequestKey(serialized);
  }, [params]);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setMapLoading(true);
    void tibiaMapApi.bootstrap(floor, controller.signal)
      .then((value) => {
        if (current) setBootstrap(value);
      })
      .catch(() => { if (current && !controller.signal.aborted) setBootstrap(null); })
      .finally(() => { if (current) setMapLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [floor]);

  const selectResult = (
    row: TibiaMapResult | null,
    updateUrl = true,
    remember = true,
    preferredLocation?: string | null,
  ) => {
    setSelected(row);
    const evidence = row?.spatial_evidence?.find((item) => item.label === preferredLocation)
      || row?.spatial_evidence?.[0]
      || (row?.x != null && row.y != null
        ? {
            x: row.x,
            y: row.y,
            z: row.z,
            bounds: row.bounds,
            label: row.name,
            spatial_state: row.bounds ? 'resolved_area' as const : 'resolved_point' as const,
          }
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
        if (row.canonical_entity_id) next.set('entity', row.canonical_entity_id);
        if (row.slug) next.set('slug', row.slug);
      }
      next.set('floor', String(evidence?.z ?? floor));
      setSearchRequestedSelection(requestedMapSelection(next));
      replaceParams(next);
    }
  };

  const activeLayersKey = [...activeLayers].sort().join(',');
  useEffect(() => {
    const isolated = Boolean(selected || requestedSelection || query.trim().length >= 2);
    if (!bootstrap || !viewport || viewport.floor !== floor || isolated || !activeLayersKey) return undefined;
    const controller = new AbortController();
    const sequence = ++viewportRequestSequence.current;
    const requested = activeLayersKey.split(',') as TibiaMapLayer[];
    const timer = window.setTimeout(() => {
      setLayerStates(Object.fromEntries(requested.map((layer) => [layer, 'loading'])));
      void tibiaMapApi.viewport(viewport, requested, controller.signal)
        .then((value) => {
          if (controller.signal.aborted || sequence !== viewportRequestSequence.current) return;
          const grouped = Object.fromEntries(requested.map((layer) => [
            layer,
            value.items.filter((row) => row.entity_type === layer),
          ])) as Partial<Record<TibiaMapLayer, TibiaMapResult[]>>;
          setLayerResults(grouped);
          setLayerStates(Object.fromEntries(requested.map((layer) => [layer, 'ready'])));
        })
        .catch(() => {
          if (!controller.signal.aborted && sequence === viewportRequestSequence.current) {
            setLayerStates(Object.fromEntries(requested.map((layer) => [layer, 'error'])));
          }
        });
    }, 275);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [activeLayersKey, bootstrap, floor, query, requestedSelection, selected, viewport]);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResults([]);
      setSearchLoading(false);
      setSearchError(false);
      return undefined;
    }
    const controller = new AbortController();
    let current = true;
    const timer = window.setTimeout(() => {
      setSearchLoading(true);
      setSearchError(false);
      void tibiaMapApi.search(normalized, controller.signal)
        .then((data) => {
          if (!current) return;
          const townMatches = (bootstrap?.towns || []).filter((town) =>
            town.name.toLocaleLowerCase().includes(normalized.toLocaleLowerCase()),
          );
          const combined = [...townMatches, ...data];
          setResults(combined);
          const next = resolveMapSearchSelection(combined, searchRequestedSelection);
          selectResult(next, false, false, params.get('location'));
        })
        .catch(() => {
          if (current && !controller.signal.aborted) {
            setResults([]);
            setSearchError(true);
          }
        })
        .finally(() => { if (current) setSearchLoading(false); });
    }, 250);
    return () => { current = false; window.clearTimeout(timer); controller.abort(); };
  // Internal URL replacements do not restart search; external history navigation does.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootstrap?.towns, navigationRequestKey, query, searchRequestedSelection]);

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

  const visible = results;
  const selectedEvidence = useMemo(() => selected?.spatial_evidence || [], [selected?.spatial_evidence]);
  const entityMarkers = useMemo(() => {
    if (context?.markers.length) {
      return context.markers
        .filter((row) => row.z == null || row.z === floor)
        .map((row) => ({
          x: row.x,
          y: row.y,
          label: row.name,
          imageUrl: row.image_url,
          kind: 'creature' as const,
        }));
    }
    return selectedEvidence
      .filter((row) => row.z == null || row.z === floor)
      .map((row) => ({
        x: row.x,
        y: row.y,
        label: row.label || selected?.name || '',
        subtitle: row.role
          ? t(`map.roles.${row.role}`, { defaultValue: row.relationship || row.role })
          : row.relationship || undefined,
        kind: selected?.entity_type === 'town' ? 'location' as const : selected?.entity_type || 'location' as const,
      }));
  }, [context, floor, selected?.entity_type, selected?.name, selectedEvidence, t]);

  const layerMarkers = useMemo(() => {
    const values = [...activeLayers].flatMap((layer) => (layerResults[layer] || []).flatMap((row) =>
      (row.spatial_evidence || [])
        .filter((evidence) => evidence.z == null || evidence.z === floor)
        .map((evidence) => ({
          x: evidence.x,
          y: evidence.y,
          label: row.name,
          subtitle: evidence.role
            ? t(`map.roles.${evidence.role}`, { defaultValue: evidence.relationship || evidence.role })
            : undefined,
          imageUrl: row.image_url?.startsWith('/') ? row.image_url : undefined,
          kind: row.entity_type === 'town' ? 'location' as const : row.entity_type,
          resultId: row.id,
        })),
    ));
    const grouped = new Map<string, typeof values>();
    values.forEach((value) => {
      const key = `${value.x}:${value.y}:${floor}`;
      grouped.set(key, [...(grouped.get(key) || []), value]);
    });
    return [...grouped.values()].map((rows) => rows.length === 1 ? rows[0] : {
      x: rows[0].x,
      y: rows[0].y,
      label: t('map.markerGroup', { count: rows.length }),
      subtitle: `${rows.slice(0, 3).map((row) => row.label).join(' · ')}${rows.length > 3 ? ' …' : ''}`,
      kind: 'group' as const,
    });
  }, [activeLayers, floor, layerResults, t]);

  const isolatedMarkerMode = Boolean(selected || requestedSelection || query.trim().length >= 2);
  const mapMarkers = useMemo(
    () => markersForMapMode(isolatedMarkerMode, layerMarkers, entityMarkers),
    [entityMarkers, isolatedMarkerMode, layerMarkers],
  );
  const focus = focusedEvidence && (focusedEvidence.z == null || focusedEvidence.z === floor) ? focusedEvidence : null;
  const regions = useMemo(() => {
    if (focus?.bounds) return [{
      minX: focus.bounds.min_x,
      minY: focus.bounds.min_y,
      maxX: focus.bounds.max_x,
      maxY: focus.bounds.max_y,
      label: focus.label || selected?.name || '',
    }];
    if (isolatedMarkerMode) return [];
    return [...activeLayers].flatMap((layer) => (layerResults[layer] || []).flatMap((row) =>
      (row.spatial_evidence || [])
        .filter((evidence) => evidence.bounds && (evidence.z == null || evidence.z === floor))
        .map((evidence) => ({
          minX: evidence.bounds!.min_x,
          minY: evidence.bounds!.min_y,
          maxX: evidence.bounds!.max_x,
          maxY: evidence.bounds!.max_y,
          label: row.name,
        })),
    ));
  }, [activeLayers, floor, focus, isolatedMarkerMode, layerResults, selected?.name]);

  const map = bootstrap?.world_map;
  const selectedOnAnotherFloor = focusedEvidence?.z != null && focusedEvidence.z !== floor;
  const defaultResults = bootstrap?.default_results?.length ? bootstrap.default_results : bootstrap?.towns || [];
  const failedLayers = [...activeLayers].filter((layer) => layerStates[layer] === 'error');
  const loadingLayers = [...activeLayers].filter((layer) => layerStates[layer] === 'loading');
  const previewValues = Object.entries(selected?.preview || {}).filter(([, value]) =>
    value != null && value !== false && value !== '' && (!Array.isArray(value) || value.length),
  );

  const nearbyResults = useMemo<NearbyResult[]>(() => {
    if (!focusedEvidence) return [];
    const candidates = layers.flatMap((layer) => layerResults[layer] || []);
    return candidates
      .filter((row) => row.id !== selected?.id)
      .map((row) => {
        const evidence = (row.spatial_evidence || []).find((item) =>
          (item.z == null || item.z === floor),
        );
        if (!evidence) return null;
        return {
          row,
          distance: Math.round(Math.hypot(evidence.x - focusedEvidence.x, evidence.y - focusedEvidence.y)),
        };
      })
      .filter((value): value is NearbyResult => Boolean(value))
      .sort((left, right) => left.distance - right.distance)
      .slice(0, 20);
  }, [floor, focusedEvidence, layerResults, selected?.id]);

  const nearbyTabs = useMemo(() => ({
    hunt_zone: nearbyResults.filter(({ row }) => row.entity_type === 'hunt_zone'),
    npc: nearbyResults.filter(({ row }) => row.entity_type === 'npc'),
    quest: nearbyResults.filter(({ row }) => row.entity_type === 'quest'),
    other: nearbyResults.filter(({ row }) => !['hunt_zone', 'npc', 'quest'].includes(row.entity_type)),
  }), [nearbyResults]);

  const toggleLayer = (layer: TibiaMapLayer) => {
    setActiveLayers((current) => {
      const next = new Set(current);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  };

  const openRecent = (target: RecentMapTarget) => {
    if (target.entityType === 'town') {
      const town = bootstrap?.towns.find((row) => row.id === target.id);
      if (town) selectResult(town);
      return;
    }
    const next = new URLSearchParams({ q: target.name, entityType: target.entityType, floor: String(floor) });
    if (target.canonicalEntityId) next.set('entity', target.canonicalEntityId);
    if (target.slug) next.set('slug', target.slug);
    replaceParams(next);
    setSearchRequestedSelection(requestedMapSelection(next));
    setQuery(target.name);
    clearSelectionState();
    setSidebarOpen(true);
  };

  const updateSearch = (value: string) => {
    setQuery(value);
    setSearchRequestedSelection(null);
    clearSelectionState();
    const next = new URLSearchParams({ floor: String(floor) });
    if (value.trim()) next.set('q', value);
    replaceParams(next);
    if (value.trim()) setSidebarOpen(true);
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    setSearchError(false);
    setSearchRequestedSelection(null);
    clearSelectionState();
    replaceParams(new URLSearchParams({ floor: String(floor) }));
  };

  const resetLayers = () => {
    setActiveLayers(new Set(layers));
    setShowRoutes(true);
  };

  const applyQuickLayer = (layer: TibiaMapLayer | 'all') => {
    clearSearch();
    setActiveLayers(layer === 'all' ? new Set(layers) : new Set([layer]));
  };

  const applyRookgaardSearch = () => {
    updateSearch('Rookgaard');
  };

  const copyCoordinates = async () => {
    if (!focusedEvidence) return;
    const value = `${Math.round(focusedEvidence.x)}, ${Math.round(focusedEvidence.y)}, ${focusedEvidence.z ?? floor}`;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard may be blocked by the browser; coordinates remain visible for manual copy.
    }
  };

  const renderResult = (row: TibiaMapResult) => {
    const Icon = resultIcons[row.entity_type];
    return <button
      key={row.id}
      type="button"
      onClick={() => selectResult(row)}
      className="map-result-row"
      data-selected={selected?.id === row.id}
    >
      {row.image_url
        ? <img src={row.image_url} alt="" className="map-result-row__image" />
        : <Icon className="size-4 shrink-0 text-primary" />}
      <span className="min-w-0 flex-1">
        <strong className="block truncate text-sm">{row.name}</strong>
        <small className="block truncate text-content-muted">
          {row.geometry_status === 'mapped' && row.location_labels?.length
            ? row.location_labels.join(' · ')
            : row.subtitle || t(`map.layers.${row.entity_type}`, { defaultValue: t('map.town') })}
        </small>
      </span>
      {row.spatial_state === 'unresolved'
        ? <AlertTriangle className="size-3.5 shrink-0 text-warning" aria-label={t('map.unresolved')} />
        : row.geometry_status === 'knowledge_only'
          ? <Info className="size-3.5 shrink-0 text-content-muted" aria-label={t('map.knowledgeOnly')} />
          : <MapPin className="size-3.5 shrink-0 text-primary" aria-label={t('map.mapped')} />}
    </button>;
  };

  const floorControl = <div className="map-floor-control">
    <button
      type="button"
      disabled={!bootstrap?.available_floors.includes(floor - 1)}
      onClick={() => setFloor((value) => value - 1)}
      aria-label={t('map.floorUp')}
    ><ChevronUp size={17} /></button>
    <span title={t('map.internalFloor', { floor })}>{formatDisplayFloor(floor)}</span>
    <button
      type="button"
      disabled={!bootstrap?.available_floors.includes(floor + 1)}
      onClick={() => setFloor((value) => value + 1)}
      aria-label={t('map.floorDown')}
    ><ChevronDown size={17} /></button>
  </div>;

  const selectedDescription = previewString(selected, ['description', 'summary', 'notes', 'location_description'])
    || selected?.subtitle
    || null;
  const selectedDifficulty = previewString(selected, ['difficulty', 'danger', 'danger_rating']);
  const selectedExperience = previewMetric(selected, ['avg_exp_hour', 'experience_per_hour', 'exp_hour']);
  const selectedProfit = previewMetric(selected, ['avg_profit_hour', 'profit_per_hour', 'profit_hour']);
  const selectedLocations = selected?.location_labels || [];
  const selectedTypeLabel = selected
    ? t(`map.layers.${selected.entity_type}`, { defaultValue: selected.entity_type.replace(/_/g, ' ') })
    : '';

  return <div className="tibia-map-page" aria-label={t('map.title')}>
    <section className="map-workspace-hero">
      <div className="map-workspace-hero__title">
        <img src={TIBIAHUB_TITLE_ICONS.maps} alt="" draggable={false} />
        <div>
          <h1>{t('map.title')}</h1>
          <p>{copy.subtitle}</p>
        </div>
      </div>
      <p className="map-workspace-hero__motto">{copy.motto}</p>
    </section>

    <div className={`map-workspace ${sidebarOpen ? '' : 'map-workspace--sidebar-collapsed'}`}>
      {sidebarOpen ? <aside className="map-workspace-sidebar" aria-label={t('map.sidebar')}>
        <div className="map-sidebar-tabs" role="tablist" aria-label={copy.mapLayers}>
          <button type="button" role="tab" aria-selected={sidebarTab === 'layers'} data-active={sidebarTab === 'layers'} onClick={() => setSidebarTab('layers')}><Layers3 className="size-4" />{copy.layers}</button>
          <button type="button" role="tab" aria-selected={sidebarTab === 'legend'} data-active={sidebarTab === 'legend'} onClick={() => setSidebarTab('legend')}><Info className="size-4" />{copy.legend}</button>
        </div>

        <div className="map-sidebar-scroll">
          <label className="map-search-field">
            <Search className="size-4" />
            <input value={query} onChange={(event) => updateSearch(event.target.value)} placeholder={t('map.searchPlaceholder')} aria-label={t('map.searchLabel')} />
            {query ? <button type="button" onClick={clearSearch} aria-label={t('a11y.clearSearch')}><X className="size-4" /></button> : null}
          </label>

          {sidebarTab === 'layers' ? <>
            <section className="map-sidebar-section">
              <header><h2>{copy.mapLayers}</h2><button type="button" onClick={resetLayers}>{copy.reset}</button></header>
              <div className="map-layer-list">
                {layers.map((layer) => {
                  const Icon = layerIcons[layer];
                  const active = activeLayers.has(layer);
                  return <button key={layer} type="button" className="map-layer-row" data-active={active} aria-pressed={active} onClick={() => toggleLayer(layer)}>
                    <span className="map-layer-check">{active ? <Check className="size-3" /> : null}</span>
                    <Icon className="size-4 text-primary" />
                    <span>{t(`map.layers.${layer}`)}</span>
                    {layerStates[layer] === 'loading' ? <span className="map-layer-state" title={copy.loading}>…</span> : null}
                    {layerStates[layer] === 'error' ? <AlertTriangle className="ml-auto size-3.5 text-danger" /> : null}
                  </button>;
                })}
                <button type="button" className="map-layer-row" data-active={showRoutes} aria-pressed={showRoutes} onClick={() => setShowRoutes((value) => !value)}>
                  <span className="map-layer-check">{showRoutes ? <Check className="size-3" /> : null}</span>
                  <Route className="size-4 text-primary" /><span>{copy.routes}</span>
                </button>
              </div>
            </section>

            <section className="map-sidebar-section">
              <h2>{copy.filters}</h2>
              <div className="map-filter-summary">
                <div><span>{copy.floor}</span><strong>{formatDisplayFloor(floor)}</strong></div>
                <div><span>{copy.layers}</span><strong>{activeLayers.size}/{layers.length}</strong></div>
                <div><span>{copy.routes}</span><strong>{showRoutes ? t('common.yes') : '—'}</strong></div>
              </div>
            </section>

            <section className="map-sidebar-section">
              <h2>{copy.quickFilters}</h2>
              <div className="map-quick-filters">
                <button type="button" onClick={() => applyQuickLayer('all')}><Sparkles className="size-3.5" />{copy.allLayers}</button>
                <button type="button" onClick={() => applyQuickLayer('hunt_zone')}><MapPinned className="size-3.5" />{copy.huntsOnly}</button>
                <button type="button" onClick={() => applyQuickLayer('quest')}><BookOpenCheck className="size-3.5" />{copy.questsOnly}</button>
                <button type="button" onClick={applyRookgaardSearch}><MapPin className="size-3.5" />Rookgaard</button>
              </div>
            </section>

            {recentTargets.length ? <section className="map-sidebar-section">
              <h2 className="flex items-center gap-1.5"><Clock3 className="size-3.5" />{copy.recent}</h2>
              <div className="map-recent-list">{recentTargets.map((target) => <button key={target.id} type="button" onClick={() => openRecent(target)}><span>{target.name}</span><small>{t(`map.layers.${target.entityType}`, { defaultValue: target.entityType })}</small></button>)}</div>
            </section> : null}
          </> : <section className="map-sidebar-section map-legend-list">
            <h2>{copy.legend}</h2>
            {layers.map((layer) => {
              const Icon = layerIcons[layer];
              return <div key={layer}><Icon className="size-4 text-primary" /><span>{t(`map.layers.${layer}`)}</span></div>;
            })}
            <div><Route className="size-4 text-primary" /><span>{copy.routes}</span></div>
            <p>{isSpanish ? 'Los marcadores agrupados combinan entidades cercanas al alejar el mapa.' : 'Grouped markers combine nearby entities when the map is zoomed out.'}</p>
          </section>}

          {query.trim() ? <section className="map-sidebar-section map-search-results" aria-live="polite">
            <h2>{t('map.searchResults')}</h2>
            {searchLoading ? <p className="map-sidebar-message">{t('map.loading')}</p> : null}
            {searchError ? <p className="map-sidebar-message text-danger"><AlertTriangle className="size-4" />{t('map.searchError')}</p> : null}
            {!searchLoading && !searchError && query.trim().length >= 2 && !visible.length ? <p className="map-sidebar-message">{noResultsLabel}</p> : null}
            {!searchLoading && query.trim().length >= 2 ? visible.map(renderResult) : null}
          </section> : null}

          {!query.trim() && defaultResults.length ? <section className="map-sidebar-section map-search-results map-default-locations">
            <h2>{copy.towns}</h2>
            {defaultResults.slice(0, 8).map(renderResult)}
          </section> : null}
        </div>
      </aside> : null}

      <section className="map-canvas-shell" aria-label={copy.mapData}>
        {!sidebarOpen ? <button type="button" className="map-sidebar-open" onClick={() => setSidebarOpen(true)} aria-label={t('map.expandSidebar')}><PanelLeftOpen className="size-4" /><span>{copy.layers}</span></button> : null}

        <div className="map-canvas-search">
          <Search className="size-4" />
          <input value={query} onChange={(event) => updateSearch(event.target.value)} placeholder={copy.mapSearch} aria-label={t('map.searchLabel')} />
          {query ? <button type="button" onClick={clearSearch} aria-label={t('a11y.clearSearch')}><X className="size-4" /></button> : null}
        </div>

        {focusedEvidence ? <button type="button" className="map-coordinate-chip" onClick={() => void copyCoordinates()} title={copy.copyCoordinates}>
          <span><small>{copy.coordinates}</small><strong>{Math.round(focusedEvidence.x)}, {Math.round(focusedEvidence.y)}, {focusedEvidence.z ?? floor}</strong></span><Copy className="size-4" />
        </button> : null}
        <div className="map-compass" aria-hidden="true"><span>N</span><Compass /></div>

        <div className="map-canvas-viewer">
          {map ? <Suspense fallback={<div className="grid h-full place-items-center text-content-muted">{t('map.loading')}</div>}>
            <TibiaMapViewer
              imageUrl={map.image_url}
              label={selected?.name || t('map.title')}
              floor={floor}
              floorLabel={t('map.floor', { floor: formatDisplayFloor(floor) })}
              mapBounds={map.bounds}
              center={focus ? { x: focus.x, y: focus.y } : undefined}
              focusBounds={focus?.bounds ? {
                minX: focus.bounds.min_x,
                minY: focus.bounds.min_y,
                maxX: focus.bounds.max_x,
                maxY: focus.bounds.max_y,
              } : undefined}
              markers={mapMarkers}
              onViewportChange={setViewport}
              onMarkerSelect={(marker) => {
                if (!marker.resultId) return;
                const row = [...activeLayers]
                  .flatMap((layer) => layerResults[layer] || [])
                  .find((candidate) => candidate.id === marker.resultId);
                if (row) selectResult(row);
              }}
              regions={regions}
              paths={showRoutes ? (context?.routes || []).map((route) => ({ id: route.id, label: route.name, points: route.points })) : []}
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
        </div>

        {selected && focusedEvidence ? <div className="map-selection-pill">
          {selected.image_url ? <img src={selected.image_url} alt="" /> : <MapPin className="size-5 text-primary" />}
          <span><strong>{selected.name}</strong><small>{Math.round(focusedEvidence.x)}, {Math.round(focusedEvidence.y)}, {focusedEvidence.z ?? floor}</small></span>
        </div> : null}

        {loadingLayers.length ? <div className="map-canvas-status">{t('map.layerLoading', { count: loadingLayers.length })}</div> : null}
        {failedLayers.length ? <div className="map-canvas-status map-canvas-status--error"><AlertTriangle className="size-3.5" />{t('map.layerFailed', { layers: failedLayers.map((layer) => t(`map.layers.${layer}`)).join(', ') })}</div> : null}
      </section>

      <aside className="map-inspector" aria-label={selected?.name || t('plannerRecovery.inspector')}>
        {selected ? <>
          <header className="map-inspector-header">
            <div className="map-inspector-heading">
              {selected.image_url ? <img src={selected.image_url} alt="" /> : <MapPinned className="size-9 text-primary" />}
              <div><h2>{selected.name}</h2><p>{selectedTypeLabel}{selectedLocations.length ? ` · ${selectedLocations[0]}` : ''}</p></div>
            </div>
            <button type="button" onClick={clearSearch} aria-label={t('a11y.clearSearch')}><X className="size-4" /></button>
          </header>

          {(selectedDifficulty || selectedExperience || selectedProfit) ? <div className="map-inspector-badges">
            {selectedDifficulty ? <span>{selectedDifficulty}</span> : null}
            {selectedExperience ? <span>EXP {selectedExperience}</span> : null}
            {selectedProfit ? <span>{isSpanish ? 'Ganancia' : 'Profit'} {selectedProfit}</span> : null}
          </div> : null}

          <section className="map-inspector-visual">
            {selected.image_url ? <img src={selected.image_url} alt={selected.name} /> : <img src={TIBIAHUB_TITLE_ICONS.maps} alt="" />}
            <div><span>{selectedTypeLabel}</span><strong>{selected.name}</strong></div>
          </section>

          {focusedEvidence ? <section className="map-inspector-coordinates">
            <div><small>{copy.coordinates}</small><strong>{Math.round(focusedEvidence.x)}, {Math.round(focusedEvidence.y)}, {focusedEvidence.z ?? floor}</strong></div>
            <button type="button" onClick={() => void copyCoordinates()} aria-label={copy.copyCoordinates}><Copy className="size-4" /></button>
          </section> : null}

          {selectedLocations.length ? <div className="map-inspector-location"><MapPin className="size-4 text-primary" /><span>{copy.location}</span><strong>{selectedLocations.join(' · ')}</strong></div> : null}

          {selectedDescription ? <p className="map-inspector-description">{selectedDescription}</p> : null}

          {selectedOnAnotherFloor ? <button type="button" onClick={() => setFloor(focusedEvidence?.z as number)} className="app-button-secondary app-button-sm mx-3">{t('map.returnToFloor', { floor: formatDisplayFloor(focusedEvidence?.z as number) })}</button> : null}

          {selectedEvidence.length > 1 ? <section className="map-inspector-section">
            <h3>{copy.location}</h3>
            <div className="map-evidence-chips">{selectedEvidence.map((value, index) => <button key={`${value.x}:${value.y}:${value.z}:${index}`} type="button" onClick={() => { setFocusedEvidence(value); if (value.z != null) setFloor(value.z); }} data-active={focusedEvidence === value}>{value.label || t('map.mappedLocation', { index: index + 1 })}</button>)}</div>
          </section> : null}

          {context?.creatures.length ? <section className="map-inspector-section">
            <h3>{copy.creatures}<span>{context.creatures.length}</span></h3>
            <div className="map-inspector-creatures">{context.creatures.slice(0, 6).map((creature) => <Link key={creature.id} to={`/creatures/${creature.slug || creature.id}`} title={`${creature.name} · ${creature.hitpoints ?? t('common.unknown')} HP · ${creature.experience ?? t('common.unknown')} EXP`}><img src={creature.image_url} alt="" /><span>{creature.name}</span></Link>)}</div>
          </section> : null}

          {previewValues.length ? <section className="map-inspector-section">
            <h3>{copy.details}</h3>
            <dl className="map-inspector-details">{previewValues.slice(0, 8).map(([key, value]) => <div key={key}><dt>{t(`map.preview.${key}`, { defaultValue: key.replace(/_/g, ' ') })}</dt><dd>{Array.isArray(value) ? value.join(', ') : typeof value === 'boolean' ? t('common.yes') : String(value)}</dd></div>)}</dl>
          </section> : null}

          <section className="map-inspector-section map-nearby-section">
            <h3>{copy.nearby}</h3>
            <div className="map-nearby-tabs" role="tablist" aria-label={copy.nearby}>
              {([
                ['hunt_zone', copy.huntZones],
                ['npc', copy.npcs],
                ['quest', copy.quests],
                ['other', copy.other],
              ] as Array<[NearbyTab, string]>).map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={nearbyTab === key} data-active={nearbyTab === key} onClick={() => setNearbyTab(key)}>{label}<span>{nearbyTabs[key].length}</span></button>)}
            </div>
            <div className="map-nearby-list">
              {nearbyTabs[nearbyTab].slice(0, 5).map(({ row, distance }) => {
                const Icon = resultIcons[row.entity_type];
                return <button key={row.id} type="button" onClick={() => selectResult(row)}><Icon className="size-4 text-primary" /><span>{row.name}</span><small>{distance} {copy.distance}</small></button>;
              })}
              {!nearbyTabs[nearbyTab].length ? <p>{copy.noNearby}</p> : null}
            </div>
          </section>

          <footer className="map-inspector-actions">
            {focusedEvidence ? <button type="button" className="app-button-secondary app-button-sm" onClick={() => void copyCoordinates()}><Copy className="size-4" />{copy.copyCoordinates}</button> : null}
            {selected.to ? <Link to={selected.to} className="app-button-primary app-button-sm"><BookOpenCheck className="size-4" />{copy.openDetails}</Link> : null}
          </footer>
        </> : <div className="map-inspector-empty">
          <img src={TIBIAHUB_TITLE_ICONS.maps} alt="" />
          <h2>{t('map.title')}</h2>
          <p>{copy.selectedHint}</p>
          {recentTargets.length ? <div className="map-inspector-recent">{recentTargets.slice(0, 4).map((target) => <button key={target.id} type="button" onClick={() => openRecent(target)}><Clock3 className="size-3.5" /><span>{target.name}</span></button>)}</div> : null}
        </div>}

        {map ? <p className="map-inspector-attribution">{map.attribution} · {map.upstream_commit.slice(0, 12)}</p> : null}
      </aside>
    </div>
  </div>;
}
