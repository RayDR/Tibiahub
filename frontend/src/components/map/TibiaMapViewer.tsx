import L, { type LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { ImageOverlay, MapContainer, Marker, Polyline, Popup, Rectangle, useMap } from 'react-leaflet';

export interface MapMarker { x: number; y: number; label: string; imageUrl?: string; subtitle?: string; kind?: 'entity' | 'town' }
export interface MapPath { id: string; label: string; points: Array<{ x: number; y: number; z?: number | null }> }
export interface TibiaMapViewerProps {
  imageUrl?: string; pathfindingUrl?: string | null; showPathfinding?: boolean;
  label?: string; floor?: number | null; mapBounds?: Record<string, unknown> | null;
  center?: { x: number; y: number }; markers?: MapMarker[]; paths?: MapPath[];
  regions?: Array<{ minX: number; minY: number; maxX: number; maxY: number; label: string }>;
  coordinateMode?: 'legacy-image' | 'world'; emptyMessage?: string; resetLabel?: string;
  zoomInLabel?: string; zoomOutLabel?: string; floorLabel?: string; fill?: boolean;
  controlFooter?: ReactNode; showFloorBadge?: boolean;
}

interface LoadedMap { objectUrl: string; width: number; height: number }

function isLocalMapEndpoint(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin && (/\/api\/v1\/hunt-zones\/\d+\/map-image$/.test(url.pathname) || /\/api\/v1\/map\/floors\/\d+\/(image|pathfinding)$/.test(url.pathname));
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

function Recenter({ position, zoom }: { position?: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => { if (position) map.flyTo(position, Math.max(map.getZoom(), zoom), { duration: 0.45 }); }, [map, position, zoom]);
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

function markerIcon(marker: MapMarker): L.DivIcon {
  const content = marker.imageUrl && marker.imageUrl.startsWith('/')
    ? `<img src="${marker.imageUrl.replace(/"/g, '&quot;')}" alt="" />`
    : '<span></span>';
  return L.divIcon({ className: 'tibia-map-sprite-marker', html: content, iconSize: [38, 38], iconAnchor: [19, 34], popupAnchor: [0, -32] });
}

function townLabelIcon(label: string): L.DivIcon {
  const safeLabel = label.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  return L.divIcon({ className: 'tibia-map-town-label', html: `<span>${safeLabel}</span>`, iconSize: [0, 0], iconAnchor: [0, 0] });
}

export default function TibiaMapViewer({ imageUrl, pathfindingUrl, showPathfinding = false, label = '', floor, mapBounds, center, markers = [], paths = [], regions = [], coordinateMode = 'legacy-image', emptyMessage = '', resetLabel = '', zoomInLabel = '', zoomOutLabel = '', floorLabel, fill = false, controlFooter, showFloorBadge = true }: TibiaMapViewerProps) {
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
  const valid = (x: number, y: number) => Boolean(tibiaBounds && x >= tibiaBounds.minX && x < tibiaBounds.maxX && y >= tibiaBounds.minY && y < tibiaBounds.maxY);
  const renderedCenter = useMemo(() => {
    if (!center || !convert || !tibiaBounds || center.x < tibiaBounds.minX || center.x >= tibiaBounds.maxX || center.y < tibiaBounds.minY || center.y >= tibiaBounds.maxY) return undefined;
    return convert(center.x, center.y);
  }, [center?.x, center?.y, convert, tibiaBounds]);
  const renderedMarkers = useMemo(() => {
    if (!convert) return [];
    const values = [...markers];
    if (center && !values.some((item) => item.x === center.x && item.y === center.y)) values.unshift({ ...center, label });
    return values.filter((item) => valid(item.x, item.y)).map((item) => ({ ...item, position: convert(item.x, item.y) }));
  }, [center, convert, label, markers, tibiaBounds]);
  const renderedRegions = useMemo(() => !convert ? [] : regions.filter((item) => valid(item.minX, item.minY) && valid(item.maxX - 1, item.maxY - 1)).map((item) => ({ ...item, position: [convert(item.minX, item.minY), convert(item.maxX, item.maxY)] as LatLngBoundsExpression })), [convert, regions, tibiaBounds]);
  const renderedPaths = useMemo(() => !convert ? [] : paths.map((path) => ({ ...path, positions: path.points.filter((point) => valid(point.x, point.y) && (point.z == null || point.z === floor)).map((point) => convert(point.x, point.y)) })).filter((path) => path.positions.length >= 2), [convert, floor, paths, tibiaBounds]);

  if (loading) return <div className={`grid place-items-center bg-surface-base/60 text-sm text-content-muted ${fill ? 'h-full min-h-0' : 'min-h-56 rounded-xl border border-line'}`} role="status">{label}</div>;
  if (!loaded || !imageBounds) return <div className="rounded-xl border border-line bg-surface-base/60 px-4 py-5 text-sm text-content-muted">{emptyMessage}</div>;
  return <div className={`relative isolate z-base w-full overflow-hidden bg-surface-base ${fill ? 'h-full min-h-0' : 'h-[clamp(17rem,50vw,30rem)] rounded-xl border border-line'}`} aria-label={label}>
    <MapContainer ref={setMap} crs={L.CRS.Simple} bounds={imageBounds} maxBounds={imageBounds} maxBoundsViscosity={0.85} minZoom={-4} maxZoom={5} zoomSnap={0.5} zoomDelta={0.5} wheelPxPerZoomLevel={90} zoomControl={false} scrollWheelZoom touchZoom="center" doubleClickZoom dragging attributionControl={false} className="relative isolate z-base h-full w-full">
      <ImageOverlay url={loaded.objectUrl} bounds={imageBounds} opacity={1} />
      {showPathfinding && pathfindingUrl && isLocalMapEndpoint(pathfindingUrl) ? <ImageOverlay url={pathfindingUrl} bounds={imageBounds} opacity={0.22} /> : null}
      {renderedRegions.map((region) => <Rectangle key={`${region.label}:${region.minX}:${region.minY}`} bounds={region.position} pathOptions={{ color: 'var(--primary)', fillColor: 'var(--primary)', fillOpacity: 0.18, weight: 2 }}><Popup>{region.label}</Popup></Rectangle>)}
      {renderedPaths.map((path) => <Polyline key={path.id} positions={path.positions} pathOptions={{ color: 'var(--primary)', weight: 4, opacity: 0.9 }}><Popup>{path.label}</Popup></Polyline>)}
      {renderedMarkers.map((marker) => <Marker key={`${marker.kind || 'entity'}:${marker.x}:${marker.y}:${marker.label}`} position={marker.position} icon={marker.kind === 'town' ? townLabelIcon(marker.label) : markerIcon(marker)} interactive={marker.kind !== 'town'}>{marker.kind !== 'town' ? <Popup><strong>{marker.label}</strong>{marker.subtitle ? <small className="block">{marker.subtitle}</small> : null}</Popup> : null}</Marker>)}
      <InitialViewport bounds={imageBounds} enabled={!center} />
      <Recenter position={renderedCenter} zoom={coordinateMode === 'world' ? 2 : 0} />
      <MapLifecycle />
    </MapContainer>
    <Controls map={map} bounds={imageBounds} labels={[zoomInLabel, zoomOutLabel, resetLabel]}>{controlFooter}</Controls>
    {showFloorBadge && floor != null ? <div className="pointer-events-none absolute bottom-3 left-3 z-map-overlay rounded-lg border border-line bg-surface-overlay px-3 py-1.5 text-xs font-semibold text-content-primary">{floorLabel || floor}</div> : null}
  </div>;
}
