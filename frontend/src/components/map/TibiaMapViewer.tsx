import L, { type LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { ImageOverlay, MapContainer, Marker, Polyline, Popup, Rectangle, useMap } from 'react-leaflet';

export type MapMarkerKind = 'location' | 'npc' | 'creature' | 'boss' | 'quest' | 'hunt_zone' | 'item' | 'group' | 'town';
export interface MapMarker { x: number; y: number; label: string; imageUrl?: string; subtitle?: string; kind?: MapMarkerKind; resultId?: string }
export interface MapPath { id: string; label: string; points: Array<{ x: number; y: number; z?: number | null }> }
export interface TibiaMapViewerProps {
  imageUrl?: string;
  label?: string; floor?: number | null; mapBounds?: Record<string, unknown> | null;
  center?: { x: number; y: number }; markers?: MapMarker[]; paths?: MapPath[];
  focusBounds?: { minX: number; minY: number; maxX: number; maxY: number };
  regions?: Array<{ minX: number; minY: number; maxX: number; maxY: number; label: string }>;
  coordinateMode?: 'legacy-image' | 'world'; emptyMessage?: string; resetLabel?: string;
  zoomInLabel?: string; zoomOutLabel?: string; floorLabel?: string; fill?: boolean;
  controlFooter?: ReactNode; showFloorBadge?: boolean; onMarkerSelect?: (marker: MapMarker) => void;
  onViewportChange?: (viewport: { minX: number; minY: number; maxX: number; maxY: number; zoom: number; floor: number }) => void;
}

interface LoadedMap { objectUrl: string; width: number; height: number }

function isLocalMapEndpoint(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin && (/\/api\/v1\/hunt-zones\/\d+\/map-image$/.test(url.pathname) || /\/api\/v1\/map\/floors\/\d+\/image$/.test(url.pathname));
  } catch { return false; }
}

function readBounds(bounds: Record<string, unknown> | null | undefined) {
  if (!bounds) return null;
  const number = (...keys: string[]) => { const value = keys.map((key) => bounds[key]).find((candidate) => typeof candidate === 'number'); return typeof value === 'number' && Number.isFinite(value) ? value : null; };
  const minX = number('minX', 'min_x'); const minY = number('minY', 'min_y'); const maxX = number('maxX', 'max_x'); const maxY = number('maxY', 'max_y');
  return minX != null && minY != null && maxX != null && maxY != null && maxX > minX && maxY > minY ? { minX, minY, maxX, maxY } : null;
}

function Controls({ map, bounds, labels, children }: { map: L.Map | null; bounds: LatLngBoundsExpression; labels: [string, string, string]; children?: ReactNode }) {
  return <div className="absolute right-3 top-3 z-map-overlay flex flex-col gap-2">
    <div className="overflow-hidden rounded-xl border border-line bg-surface-overlay shadow-lg backdrop-blur">
      <button type="button" disabled={!map} aria-label={labels[0]} title={labels[0]} onClick={() => { if (map) map.zoomIn(); }} className="grid size-10 place-items-center border-b border-line text-content-primary hover:bg-surface-hover disabled:opacity-40"><Plus size={17} /></button>
      <button type="button" disabled={!map} aria-label={labels[1]} title={labels[1]} onClick={() => { if (map) map.zoomOut(); }} className="grid size-10 place-items-center border-b border-line text-content-primary hover:bg-surface-hover disabled:opacity-40"><Minus size={17} /></button>
      <button type="button" disabled={!map} aria-label={labels[2]} title={labels[2]} onClick={() => { if (map) map.fitBounds(bounds, { padding: [0, 0] }); }} className="grid size-10 place-items-center text-content-primary hover:bg-surface-hover disabled:opacity-40"><RotateCcw size={16} /></button>
    </div>
    {children}
  </div>;
}

function InitialViewport({ bounds, enabled }: { bounds: LatLngBoundsExpression; enabled: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!enabled) return undefined;
    const frame = window.requestAnimationFrame(() => {
      map.fitBounds(bounds, { animate: false, padding: [0, 0] });
      map.setZoom(Math.min(map.getBoundsZoom(bounds) + 0.5, map.getMaxZoom()), { animate: false });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [bounds, enabled, map]);
  return null;
}

function FocusViewport({ position, bounds, zoom }: { position?: [number, number]; bounds?: LatLngBoundsExpression; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { animate: true, duration: 0.45, padding: [48, 48], maxZoom: 3 });
    } else if (position) {
      map.flyTo(position, Math.max(map.getZoom(), zoom), { duration: 0.45 });
    }
  }, [bounds, map, position, zoom]);
  return null;
}

function MapLifecycle() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const refresh = () => map.invalidateSize({ pan: false });
    const observer = new ResizeObserver(refresh);
    observer.observe(container);
    const frame = window.requestAnimationFrame(refresh);
    return () => { observer.disconnect(); window.cancelAnimationFrame(frame); };
  }, [map]);
  return null;
}

function ViewportReporter({
  loaded,
  bounds,
  floor,
  enabled,
  onChange,
}: {
  loaded: LoadedMap;
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
  floor: number | null | undefined;
  enabled: boolean;
  onChange?: TibiaMapViewerProps['onViewportChange'];
}) {
  const map = useMap();
  useEffect(() => {
    if (!enabled || floor == null || !onChange) return undefined;
    const report = () => {
      const visible = map.getBounds();
      const toX = (pixel: number) => bounds.minX + (pixel / loaded.width) * (bounds.maxX - bounds.minX);
      const toY = (pixel: number) => bounds.minY + (pixel / loaded.height) * (bounds.maxY - bounds.minY);
      const minX = Math.max(bounds.minX, Math.floor(toX(visible.getWest())));
      const minY = Math.max(bounds.minY, Math.floor(toY(visible.getSouth())));
      const maxX = Math.min(bounds.maxX, Math.ceil(toX(visible.getEast())));
      const maxY = Math.min(bounds.maxY, Math.ceil(toY(visible.getNorth())));
      if (minX < maxX && minY < maxY) onChange({ minX, minY, maxX, maxY, zoom: map.getZoom(), floor });
    };
    map.on('moveend zoomend', report);
    const frame = window.requestAnimationFrame(report);
    return () => { map.off('moveend zoomend', report); window.cancelAnimationFrame(frame); };
  }, [bounds, enabled, floor, loaded, map, onChange]);
  return null;
}

function markerFallbackSvg(kind: MapMarkerKind): string {
  const attrs = 'viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  if (kind === 'creature') return `<svg ${attrs}><circle cx="8" cy="7" r="2"/><circle cx="16" cy="7" r="2"/><circle cx="5.5" cy="12.5" r="1.7"/><circle cx="18.5" cy="12.5" r="1.7"/><path d="M12 11c-4 0-7 3.5-7 7 0 1.7 1.2 2.7 2.8 2.7 1.3 0 2.3-1.2 4.2-1.2s2.9 1.2 4.2 1.2c1.6 0 2.8-1 2.8-2.7 0-3.5-3-7-7-7Z"/></svg>`;
  if (kind === 'boss') return `<svg ${attrs}><path d="M5.5 9.5C5.5 4.8 8.2 2 12 2s6.5 2.8 6.5 7.5c0 2.8-1.2 4.8-3.2 6.2V21l-2.1-1.8L12 22l-1.2-2.8L8.7 21v-5.3c-2-1.4-3.2-3.4-3.2-6.2Z"/><circle cx="9.5" cy="9" r="1.2"/><circle cx="14.5" cy="9" r="1.2"/><path d="m10.5 13 1.5-1.5 1.5 1.5M8.5 15.5h7"/></svg>`;
  if (kind === 'item') return `<svg ${attrs}><path d="M9 3c1 1.8 2 2.5 3 2.5S14 4.8 15 3l2 2.5-2 2.5H9L7 5.5 9 3Z"/><path d="M9 8c-3.5 3.5-5 6.8-5 9.5C4 21 7 22 12 22s8-1 8-4.5c0-2.7-1.5-6-5-9.5"/><path d="M9.5 15.5c1.6 1 3.4 1 5 0"/></svg>`;
  if (kind === 'quest') return `<svg ${attrs}><path d="M6 3h12v17H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Z"/><path d="M6 3v17M9 8h6M9 12h5"/><path d="m14 16 1.5 1 1.5-1v5l-1.5-1-1.5 1v-5Z"/></svg>`;
  if (kind === 'hunt_zone') return `<svg ${attrs}><circle cx="12" cy="12" r="9"/><path d="m15 7-2.3 5.7L7 15l2.3-5.7L15 7Z"/><path d="M12 1v3M12 20v3M1 12h3M20 12h3"/></svg>`;
  if (kind === 'npc') return `<svg ${attrs}><circle cx="9" cy="8" r="3"/><circle cx="16.5" cy="8.5" r="2.5"/><path d="M3 20c.6-4.5 2.6-7 6-7s5.4 2.5 6 7M14 14c1-.8 2-1.2 3.2-1.2 2.8 0 4.3 2.3 4.8 5.7"/></svg>`;
  if (kind === 'group') return `<svg ${attrs}><path d="M12 5v14M5 12h14"/></svg>`;
  return `<svg ${attrs}><path d="M12 22s7-6.2 7-13a7 7 0 1 0-14 0c0 6.8 7 13 7 13Z"/><circle cx="12" cy="9" r="2.5"/></svg>`;
}

function markerIcon(marker: MapMarker): L.DivIcon {
  const markerKind = marker.kind || 'location';
  const requestedImage = marker.imageUrl?.startsWith('/')
    ? marker.imageUrl
    : markerKind === 'npc'
      ? `/api/v1/npcs/${encodeURIComponent(marker.label)}/image`
      : null;
  const localImage = requestedImage
    ? encodeURI(requestedImage)
        .replace(/'/g, '%27')
        .replace(/"/g, '%22')
        .replace(/\(/g, '%28')
        .replace(/\)/g, '%29')
    : null;
  const imageLayer = localImage
    ? `<span class="tibia-map-pin-image" style="background-image:url('${localImage}')" aria-hidden="true"></span>`
    : '';
  const html = `<span class="tibia-map-pin-head"><span class="tibia-map-pin-fallback" aria-hidden="true">${markerFallbackSvg(markerKind)}</span>${imageLayer}</span><span class="tibia-map-pin-tip" aria-hidden="true"></span>`;
  return L.divIcon({
    className: `tibia-map-pin tibia-map-pin--${markerKind}`,
    html,
    iconSize: [42, 52],
    iconAnchor: [21, 50],
    popupAnchor: [0, -48],
  });
}

function townLabelIcon(label: string): L.DivIcon {
  const safeLabel = label.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return L.divIcon({ className: 'tibia-map-town-label', html: `<span>${safeLabel}</span>`, iconSize: [0, 0], iconAnchor: [0, 0] });
}

export default function TibiaMapViewer({ imageUrl, label = '', floor, mapBounds, center, focusBounds, markers = [], paths = [], regions = [], coordinateMode = 'legacy-image', emptyMessage = '', resetLabel = '', zoomInLabel = '', zoomOutLabel = '', floorLabel, fill = false, controlFooter, showFloorBadge = true, onMarkerSelect, onViewportChange }: TibiaMapViewerProps) {
  const [loaded, setLoaded] = useState<LoadedMap | null>(null); const [loading, setLoading] = useState(Boolean(imageUrl)); const [map, setMap] = useState<L.Map | null>(null);
  useEffect(() => {
    const controller = new AbortController(); let objectUrl: string | null = null; setLoaded(null);
    if (!imageUrl || !isLocalMapEndpoint(imageUrl)) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    void fetch(imageUrl, { signal: controller.signal, credentials: 'same-origin' }).then(async (response) => {
      if (!response.ok) throw new Error('map unavailable'); const blob = await response.blob(); objectUrl = URL.createObjectURL(blob);
      const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => { const image = new Image(); image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight }); image.onerror = reject; image.src = objectUrl as string; });
      if (!controller.signal.aborted && objectUrl) setLoaded({ objectUrl, ...dimensions });
    }).catch(() => { if (!controller.signal.aborted) setLoaded(null); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [imageUrl]);

  const imageBounds = useMemo<LatLngBoundsExpression | null>(() => loaded ? [[0, 0], [loaded.height, loaded.width]] : null, [loaded]);
  const tibiaBounds = useMemo(() => readBounds(mapBounds), [mapBounds]);
  const convert = useMemo(() => !loaded || !tibiaBounds ? null : (x: number, y: number): [number, number] => {
    const py = ((y - tibiaBounds.minY) / (tibiaBounds.maxY - tibiaBounds.minY)) * loaded.height;
    const px = ((x - tibiaBounds.minX) / (tibiaBounds.maxX - tibiaBounds.minX)) * loaded.width;
    return [coordinateMode === 'world' ? py : loaded.height - py, px];
  }, [coordinateMode, loaded, tibiaBounds]);
  const valid = useCallback((x: number, y: number) => Boolean(tibiaBounds && x >= tibiaBounds.minX && x < tibiaBounds.maxX && y >= tibiaBounds.minY && y < tibiaBounds.maxY), [tibiaBounds]);
  const renderedCenter = useMemo(() => {
    if (!center || !convert || !tibiaBounds || center.x < tibiaBounds.minX || center.x >= tibiaBounds.maxX || center.y < tibiaBounds.minY || center.y >= tibiaBounds.maxY) return undefined;
    return convert(center.x, center.y);
  }, [center, convert, tibiaBounds]);
  const renderedFocusBounds = useMemo<LatLngBoundsExpression | undefined>(() => {
    if (!focusBounds || !convert || !valid(focusBounds.minX, focusBounds.minY) || !valid(focusBounds.maxX - 1, focusBounds.maxY - 1)) return undefined;
    return [convert(focusBounds.minX, focusBounds.minY), convert(focusBounds.maxX, focusBounds.maxY)];
  }, [convert, focusBounds, valid]);
  const renderedMarkers = useMemo(() => {
    if (!convert) return [];
    const values = [...markers];
    if (center && !values.some((item) => item.x === center.x && item.y === center.y)) values.unshift({ ...center, label });
    return values.filter((item) => valid(item.x, item.y)).map((item) => ({ ...item, position: convert(item.x, item.y) }));
  }, [center, convert, label, markers, valid]);
  const renderedRegions = useMemo(() => !convert ? [] : regions.filter((item) => valid(item.minX, item.minY) && valid(item.maxX - 1, item.maxY - 1)).map((item) => ({ ...item, position: [convert(item.minX, item.minY), convert(item.maxX, item.maxY)] as LatLngBoundsExpression })), [convert, regions, valid]);
  const renderedPaths = useMemo(() => !convert ? [] : paths.map((path) => ({ ...path, positions: path.points.filter((point) => valid(point.x, point.y) && (point.z == null || point.z === floor)).map((point) => convert(point.x, point.y)) })).filter((path) => path.positions.length >= 2), [convert, floor, paths, valid]);

  if (loading) return <div className={`grid place-items-center bg-surface-base/60 text-sm text-content-muted ${fill ? 'h-full min-h-0' : 'min-h-56 rounded-xl border border-line'}`} role="status">{label}</div>;
  if (!loaded || !imageBounds) return <div className="rounded-xl border border-line bg-surface-base/60 px-4 py-5 text-sm text-content-muted">{emptyMessage}</div>;
  return <div className={`relative isolate z-base w-full overflow-hidden bg-surface-base ${fill ? 'h-full min-h-0' : 'h-[clamp(17rem,50vw,30rem)] rounded-xl border border-line'}`} aria-label={label}>
    <MapContainer ref={setMap} crs={L.CRS.Simple} bounds={imageBounds} maxBounds={imageBounds} maxBoundsViscosity={0.85} minZoom={-4} maxZoom={5} zoomSnap={0.5} zoomDelta={0.5} wheelPxPerZoomLevel={90} zoomControl={false} scrollWheelZoom touchZoom="center" doubleClickZoom dragging attributionControl={false} className="relative isolate z-base h-full w-full">
      <ImageOverlay url={loaded.objectUrl} bounds={imageBounds} opacity={1} />
      {renderedRegions.map((region) => <Rectangle key={`${region.label}:${region.minX}:${region.minY}`} bounds={region.position} pathOptions={{ color: 'var(--primary)', fillColor: 'var(--primary)', fillOpacity: 0.18, weight: 2 }}><Popup>{region.label}</Popup></Rectangle>)}
      {renderedPaths.map((path) => <Polyline key={path.id} positions={path.positions} pathOptions={{ color: 'var(--primary)', weight: 4, opacity: 0.9 }}><Popup>{path.label}</Popup></Polyline>)}
      {renderedMarkers.map((marker) => <Marker key={`${marker.kind || 'entity'}:${marker.x}:${marker.y}:${marker.label}`} position={marker.position} icon={marker.kind === 'town' ? townLabelIcon(marker.label) : markerIcon(marker)} interactive={marker.kind !== 'town'} eventHandlers={marker.resultId && onMarkerSelect ? { click: () => onMarkerSelect(marker) } : undefined}>{marker.kind !== 'town' ? <Popup><strong>{marker.label}</strong>{marker.subtitle ? <small className="block">{marker.subtitle}</small> : null}</Popup> : null}</Marker>)}
      <InitialViewport bounds={imageBounds} enabled={!center} />
      <FocusViewport position={renderedCenter} bounds={renderedFocusBounds} zoom={coordinateMode === 'world' ? 2 : 0} />
      {tibiaBounds ? <ViewportReporter loaded={loaded} bounds={tibiaBounds} floor={floor} enabled={coordinateMode === 'world'} onChange={onViewportChange} /> : null}
      <MapLifecycle />
    </MapContainer>
    <Controls map={map} bounds={imageBounds} labels={[zoomInLabel, zoomOutLabel, resetLabel]}>{controlFooter}</Controls>
    {showFloorBadge && floor != null ? <div className="pointer-events-none absolute bottom-3 left-3 z-map-overlay rounded-lg border border-line bg-surface-overlay px-3 py-1.5 text-xs font-semibold text-content-primary">{floorLabel || floor}</div> : null}
  </div>;
}
