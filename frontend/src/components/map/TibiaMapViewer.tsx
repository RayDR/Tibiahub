import L, { type LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, ImageOverlay, MapContainer, Popup, Rectangle, useMap } from 'react-leaflet';

export interface TibiaMapViewerProps {
  imageUrl?: string;
  label?: string;
  floor?: number | null;
  mapBounds?: Record<string, unknown> | null;
  center?: { x: number; y: number };
  markers?: Array<{ x: number; y: number; label: string }>;
  regions?: Array<{ minX: number; minY: number; maxX: number; maxY: number; label: string }>;
  zoom?: number;
  emptyMessage?: string;
  resetLabel?: string;
  zoomInLabel?: string;
  zoomOutLabel?: string;
  floorLabel?: string;
  fill?: boolean;
}

interface LoadedMap {
  objectUrl: string;
  width: number;
  height: number;
}

function isLocalMapEndpoint(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin);
    return /\/api\/v1\/hunt-zones\/\d+\/map-image$/.test(url.pathname);
  } catch {
    return false;
  }
}

function readBounds(bounds: Record<string, unknown> | null | undefined) {
  if (!bounds) return null;
  const number = (...keys: string[]) => {
    const value = keys.map((key) => bounds[key]).find((candidate) => typeof candidate === 'number');
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  };
  const minX = number('minX', 'min_x');
  const minY = number('minY', 'min_y');
  const maxX = number('maxX', 'max_x');
  const maxY = number('maxY', 'max_y');
  return minX != null && minY != null && maxX != null && maxY != null && maxX > minX && maxY > minY
    ? { minX, minY, maxX, maxY }
    : null;
}

function MapControls({ imageBounds, resetLabel, zoomInLabel, zoomOutLabel }: {
  imageBounds: LatLngBoundsExpression;
  resetLabel: string;
  zoomInLabel: string;
  zoomOutLabel: string;
}) {
  const map = useMap();
  return <div className="absolute right-3 top-3 z-[500] flex flex-col gap-1">
    <button type="button" title={zoomInLabel} aria-label={zoomInLabel} onClick={() => map.zoomIn()} className="grid size-10 place-items-center rounded-lg border border-line bg-surface-overlay text-content-primary shadow"><Plus size={17} /></button>
    <button type="button" title={zoomOutLabel} aria-label={zoomOutLabel} onClick={() => map.zoomOut()} className="grid size-10 place-items-center rounded-lg border border-line bg-surface-overlay text-content-primary shadow"><Minus size={17} /></button>
    <button type="button" title={resetLabel} aria-label={resetLabel} onClick={() => map.fitBounds(imageBounds, { padding: [12, 12] })} className="grid size-10 place-items-center rounded-lg border border-line bg-surface-overlay text-content-primary shadow"><RotateCcw size={16} /></button>
  </div>;
}

function Recenter({ position }: { position?: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.flyTo(position, Math.max(map.getZoom(), 0), { duration: 0.45 });
  }, [map, position]);
  return null;
}

export default function TibiaMapViewer({
  imageUrl,
  label = 'Tibia map',
  floor,
  mapBounds,
  center,
  markers = [],
  regions = [],
  emptyMessage = 'No local map is available for this area yet.',
  resetLabel = 'Reset map',
  zoomInLabel = 'Zoom in',
  zoomOutLabel = 'Zoom out',
  floorLabel,
  fill = false,
}: TibiaMapViewerProps) {
  const [loaded, setLoaded] = useState<LoadedMap | null>(null);
  const [loading, setLoading] = useState(Boolean(imageUrl));

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setLoaded(null);

    if (!imageUrl || !isLocalMapEndpoint(imageUrl)) {
      setLoading(false);
      return () => controller.abort();
    }

    setLoading(true);
    void fetch(imageUrl, { signal: controller.signal, credentials: 'same-origin' })
      .then(async (response) => {
        if (!response.ok) throw new Error('map unavailable');
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
          const image = new Image();
          image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
          image.onerror = reject;
          image.src = objectUrl as string;
        });
        if (!controller.signal.aborted && objectUrl) setLoaded({ objectUrl, ...dimensions });
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoaded(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageUrl]);

  const imageBounds = useMemo<LatLngBoundsExpression | null>(() => loaded
    ? [[0, 0], [loaded.height, loaded.width]]
    : null, [loaded]);
  const tibiaBounds = useMemo(() => readBounds(mapBounds), [mapBounds]);
  const trustworthyMarkers = useMemo(() => {
    if (!loaded || !tibiaBounds) return [];
    const candidates = center ? [{ ...center, label }, ...markers] : markers;
    return candidates.filter((marker) =>
      marker.x >= tibiaBounds.minX && marker.x <= tibiaBounds.maxX && marker.y >= tibiaBounds.minY && marker.y <= tibiaBounds.maxY,
    ).map((marker) => ({
      ...marker,
      position: [
        loaded.height - ((marker.y - tibiaBounds.minY) / (tibiaBounds.maxY - tibiaBounds.minY)) * loaded.height,
        ((marker.x - tibiaBounds.minX) / (tibiaBounds.maxX - tibiaBounds.minX)) * loaded.width,
      ] as [number, number],
    }));
  }, [center, label, loaded, markers, tibiaBounds]);
  const trustworthyRegions = useMemo(() => {
    if (!loaded || !tibiaBounds) return [];
    const convert = (x: number, y: number): [number, number] => [
      loaded.height - ((y - tibiaBounds.minY) / (tibiaBounds.maxY - tibiaBounds.minY)) * loaded.height,
      ((x - tibiaBounds.minX) / (tibiaBounds.maxX - tibiaBounds.minX)) * loaded.width,
    ];
    return regions.filter((region) => region.minX >= tibiaBounds.minX && region.maxX <= tibiaBounds.maxX && region.minY >= tibiaBounds.minY && region.maxY <= tibiaBounds.maxY).map((region) => ({
      ...region,
      position: [convert(region.minX, region.minY), convert(region.maxX, region.maxY)] as LatLngBoundsExpression,
    }));
  }, [loaded, regions, tibiaBounds]);

  if (loading) return <div className="grid min-h-56 place-items-center rounded-xl border border-line bg-surface-base/60 text-sm text-content-muted" role="status">{label}</div>;
  if (!loaded || !imageBounds) return <div className="rounded-xl border border-line bg-surface-base/60 px-4 py-5 text-sm text-content-muted">{emptyMessage}</div>;

  return <div className={`relative w-full overflow-hidden rounded-xl border border-line bg-surface-base ${fill ? 'h-full min-h-[28rem]' : 'h-[clamp(17rem,50vw,30rem)]'}`} aria-label={label}>
    <MapContainer crs={L.CRS.Simple} bounds={imageBounds} maxBounds={imageBounds} maxBoundsViscosity={0.85} minZoom={-4} maxZoom={4} zoomControl={false} scrollWheelZoom touchZoom dragging attributionControl={false} className="h-full w-full">
      <ImageOverlay url={loaded.objectUrl} bounds={imageBounds} opacity={1} />
      {trustworthyRegions.map((region) => <Rectangle key={`${region.label}:${region.minX}:${region.minY}`} bounds={region.position} pathOptions={{ color: 'var(--primary)', fillColor: 'var(--primary)', fillOpacity: 0.18, weight: 2 }}><Popup>{region.label}</Popup></Rectangle>)}
      {trustworthyMarkers.map((marker) => <CircleMarker key={`${marker.x}:${marker.y}:${marker.label}`} center={marker.position} radius={8} pathOptions={{ color: 'var(--warning)', fillColor: 'var(--warning)', fillOpacity: 0.75 }}><Popup>{marker.label}</Popup></CircleMarker>)}
      <Recenter position={trustworthyMarkers[0]?.position} />
      <MapControls imageBounds={imageBounds} resetLabel={resetLabel} zoomInLabel={zoomInLabel} zoomOutLabel={zoomOutLabel} />
    </MapContainer>
    {floor != null ? <div className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-lg border border-line bg-surface-overlay px-3 py-1.5 text-xs font-semibold text-content-primary">{floorLabel || floor}</div> : null}
  </div>;
}
