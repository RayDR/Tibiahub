import { ListOrdered, MapPin } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { spatialApi } from '../services/api';
import type { SpatialPointMetadata, SpatialRegionMetadata, SpatialRouteMetadata } from '../types';

export default function MapMetadataPanel({ entityId, locationIdentifier }: { entityId?: string; locationIdentifier?: string }) {
  const { t } = useTranslation();
  const [points, setPoints] = useState<SpatialPointMetadata[]>([]);
  const [regions, setRegions] = useState<SpatialRegionMetadata[]>([]);
  const [routes, setRoutes] = useState<SpatialRouteMetadata[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        if (locationIdentifier) {
          const payload = await spatialApi.forLocation(locationIdentifier, controller.signal);
          setPoints(payload.points || []); setRegions(payload.regions || []);
          const details = await Promise.all((payload.routes || []).slice(0, 10).map(
            (route: SpatialRouteMetadata) => spatialApi.route(route.id, controller.signal),
          ));
          setRoutes(details);
        } else if (entityId) {
          const payload = await spatialApi.forEntity(entityId, controller.signal);
          setPoints((payload.items || []).flatMap((item: { map_point?: SpatialPointMetadata }) => item.map_point ? [item.map_point] : []));
          setRegions((payload.items || []).flatMap((item: { map_region?: SpatialRegionMetadata }) => item.map_region ? [item.map_region] : []));
        }
      } catch {
        setPoints([]); setRegions([]); setRoutes([]);
      } finally {
        setLoaded(true);
      }
    };
    void load();
    return () => controller.abort();
  }, [entityId, locationIdentifier]);

  return <section className="mt-6 rounded-xl border border-line p-4">
    <h2 className="mb-3 flex items-center gap-2 font-semibold text-primary"><MapPin size={16} />{t('spatialMetadata.title')}</h2>
    {loaded && points.length === 0 && regions.length === 0 && routes.length === 0
      ? <div className="rounded-lg border border-dashed border-line bg-surface-base/40 p-4 text-sm text-content-secondary"><p className="font-medium text-content-secondary">{t('spatialMetadata.unavailable')}</p><p className="mt-1">{t('spatialMetadata.placeholder')}</p></div>
      : <div className="space-y-4">
        {points.map(point => <div key={point.id} className="rounded-lg bg-surface-base/60 p-3 text-sm"><p className="font-medium text-content-primary">{point.name}</p><p className="mt-1 text-content-secondary">{point.x != null ? t('spatialMetadata.coordinates', { x: point.x, y: point.y, z: point.z }) : t('spatialMetadata.unresolved')}</p></div>)}
        {regions.map(region => <div key={region.id} className="rounded-lg bg-surface-base/60 p-3 text-sm"><p className="font-medium text-content-primary">{region.name}</p><p className="mt-1 text-content-secondary">{region.bounds.min_x != null ? t('spatialMetadata.bounds', region.bounds) : t('spatialMetadata.unresolved')}</p></div>)}
        {routes.map(route => <article key={route.id} className="rounded-lg bg-surface-base/60 p-3"><h3 className="flex items-center gap-2 font-medium text-content-primary"><ListOrdered size={15} />{route.name}</h3><p className="mt-1 text-xs text-content-secondary">{t('spatialMetadata.routeEndpoints', { start: route.start_location || t('spatialMetadata.unresolved'), end: route.end_location || t('spatialMetadata.unresolved') })}</p>{route.steps && route.steps.length > 0 && <ol className="mt-3 space-y-2">{route.steps.map(step => <li key={step.id} className="flex gap-2 text-sm text-content-secondary"><span className="text-primary">{step.sequence}.</span><span>{step.instruction || step.location_name || t('spatialMetadata.unresolved')}</span></li>)}</ol>}</article>)}
      </div>}
  </section>;
}
