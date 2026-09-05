import { lazy, Suspense, useEffect, useState } from "react";
import { ListOrdered, MapPin, Radar } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { spatialApi } from "../services/api";
import { buildMapEntityUrl, tibiaMapApi, type TibiaMapBootstrap, type TibiaMapSearchType } from "../services/tibiaMap";
import type {
  SpatialPointMetadata,
  SpatialRegionMetadata,
  SpatialRouteMetadata,
} from "../types";
import { formatDisplayFloor } from "../utils/tibiaFloors";

const TibiaMapViewer = lazy(() => import('./map/TibiaMapViewer'));
const hasTrustedGeometry = (value: { confidence: string; verification_state: string }) => value.verification_state === 'verified' || value.confidence === 'verified' || value.confidence === 'high';
const hasResolvedPoint = (point: SpatialPointMetadata): point is SpatialPointMetadata & { x: number; y: number; z: number } => point.x != null && point.y != null && point.z != null;

export default function MapMetadataPanel({
  entityId,
  locationIdentifier,
  mapTarget,
}: {
  entityId?: string;
  locationIdentifier?: string;
  mapTarget?: { entityType: TibiaMapSearchType; name: string; slug?: string | null; canonicalEntityId?: string | null };
}) {
  const { t } = useTranslation();
  const [points, setPoints] = useState<SpatialPointMetadata[]>([]);
  const [regions, setRegions] = useState<SpatialRegionMetadata[]>([]);
  const [routes, setRoutes] = useState<SpatialRouteMetadata[]>([]);
  const [nearby, setNearby] = useState<
    Array<{
      source_entity_id: string;
      canonical_name: string;
      entity_type: string;
      slug: string;
      distance: number;
    }>
  >([]);
  const [loaded, setLoaded] = useState(false);
  const [mapBootstrap, setMapBootstrap] = useState<TibiaMapBootstrap | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setLoaded(false);
    setPoints([]); setRegions([]); setRoutes([]); setNearby([]); setMapBootstrap(null);
    const load = async () => {
      try {
        let nextPoints: SpatialPointMetadata[] = [];
        let nextRegions: SpatialRegionMetadata[] = [];
        let nextRoutes: SpatialRouteMetadata[] = [];
        if (locationIdentifier) {
          const payload = await spatialApi.forLocation(
            locationIdentifier,
            controller.signal,
          );
          nextPoints = (payload.points || []).filter(hasTrustedGeometry);
          nextRegions = (payload.regions || []).filter(hasTrustedGeometry);
          const origin = nextPoints.find(hasResolvedPoint);
          if (origin) {
            void spatialApi.nearby(origin.x, origin.y, origin.z, controller.signal)
              .then((value) => { if (current) setNearby(value.items || []); })
              .catch(() => { /* Nearby is optional when PostGIS is unavailable. */ });
          }
          const details = await Promise.allSettled(
            (payload.routes || [])
              .slice(0, 10)
              .map((route: SpatialRouteMetadata) =>
                spatialApi.route(route.id, controller.signal),
              ),
          );
          nextRoutes = details.flatMap((result) => result.status === 'fulfilled' && hasTrustedGeometry(result.value) ? [result.value] : []);
        } else if (entityId) {
          const payload = await spatialApi.forEntity(
            entityId,
            controller.signal,
          );
          const entityPoints = (payload.items || []).flatMap(
            (item: { map_point?: SpatialPointMetadata }) =>
              item.map_point ? [item.map_point] : [],
          );
          nextPoints = entityPoints.filter(hasTrustedGeometry);
          nextRegions = (payload.items || []).flatMap(
              (item: { map_region?: SpatialRegionMetadata }) =>
                item.map_region ? [item.map_region] : [],
            ).filter(hasTrustedGeometry);
          const origin = nextPoints.find(hasResolvedPoint);
          if (origin) {
            void spatialApi.nearby(origin.x, origin.y, origin.z, controller.signal)
              .then((value) => { if (current) setNearby(value.items || []); })
              .catch(() => { /* Nearby is optional when PostGIS is unavailable. */ });
          }
        }
        if (!current) return;
        setPoints(nextPoints); setRegions(nextRegions); setRoutes(nextRoutes);
        const pointOrigin = nextPoints.find((point) => point.x != null && point.y != null && point.z != null);
        const regionOrigin = nextRegions.find((region) => region.bounds.min_x != null && region.bounds.min_y != null && region.bounds.max_x != null && region.bounds.max_y != null && region.bounds.min_z != null);
        const floor = pointOrigin?.z ?? regionOrigin?.bounds.min_z;
        if (floor != null) {
          try {
            const bootstrap = await tibiaMapApi.bootstrap(floor, controller.signal);
            if (current) setMapBootstrap(bootstrap);
          } catch { /* Keep canonical metadata visible without a floor asset. */ }
        }
      } catch {
        if (current && !controller.signal.aborted) {
          setPoints([]); setRegions([]); setRoutes([]); setNearby([]); setMapBootstrap(null);
        }
      } finally {
        if (current) setLoaded(true);
      }
    };
    void load();
    return () => { current = false; controller.abort(); };
  }, [entityId, locationIdentifier]);

  const nearbyOrigin = points.find(
    (point) => point.x != null && point.y != null && point.z != null,
  );
  const mapOrigin = nearbyOrigin || (() => {
    const region = regions.find((value) => value.bounds.min_x != null && value.bounds.min_y != null && value.bounds.max_x != null && value.bounds.max_y != null && value.bounds.min_z != null);
    return region ? { x: ((region.bounds.min_x as number) + (region.bounds.max_x as number)) / 2, y: ((region.bounds.min_y as number) + (region.bounds.max_y as number)) / 2, z: region.bounds.min_z as number, name: region.name } : undefined;
  })();
  return (
    <section className="mt-6 overflow-hidden rounded-2xl bg-surface-raised shadow-sm">
      <div className="bg-gradient-to-r from-primary-subtle to-accent-subtle p-4">
        <h2 className="flex items-center gap-2 font-semibold text-primary">
          <MapPin size={16} />
          {t("spatialMetadata.title")}
        </h2>
        <p className="mt-1 text-sm text-content-secondary">
          {t("spatialMetadata.help")}
        </p>
      </div>
      <div className="p-4">
        {loaded &&
        points.length === 0 &&
        regions.length === 0 &&
        routes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-line bg-surface-base/40 p-4 text-sm text-content-secondary">
            <p className="font-medium text-content-secondary">
              {t("spatialMetadata.unavailable")}
            </p>
            <p className="mt-1">{t("spatialMetadata.placeholder")}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {mapOrigin && mapBootstrap?.world_map ? <><Suspense fallback={<div className="grid min-h-64 place-items-center text-content-muted">{t('map.loading')}</div>}><TibiaMapViewer imageUrl={mapBootstrap.world_map.image_url} pathfindingUrl={mapBootstrap.world_map.pathfinding_url} label={mapOrigin.name || t('spatialMetadata.preview')} floor={mapOrigin.z} floorLabel={t('map.floor', { floor: formatDisplayFloor(mapOrigin.z as number) })} mapBounds={mapBootstrap.world_map.bounds} center={{ x: mapOrigin.x as number, y: mapOrigin.y as number }} markers={points.filter((point) => point.x != null && point.y != null).map((point) => ({ x: point.x as number, y: point.y as number, label: point.name }))} regions={regions.filter((region) => region.bounds.min_x != null && region.bounds.min_y != null && region.bounds.max_x != null && region.bounds.max_y != null).map((region) => ({ minX: region.bounds.min_x as number, minY: region.bounds.min_y as number, maxX: region.bounds.max_x as number, maxY: region.bounds.max_y as number, label: region.name }))} paths={routes.map((route) => ({ id: route.id, label: route.name, points: (route.steps || []).filter((step) => step.x != null && step.y != null).map((step) => ({ x: step.x as number, y: step.y as number, z: step.z })) }))} coordinateMode="world" resetLabel={t('map.reset')} zoomInLabel={t('map.zoomIn')} zoomOutLabel={t('map.zoomOut')} emptyMessage={t('map.noBaseMap')} /></Suspense>{mapTarget ? <div className="mt-3 flex justify-end"><Link to={buildMapEntityUrl({ ...mapTarget, floor: mapOrigin.z as number, location: mapOrigin.name })} className="app-button-secondary app-button-sm">{t('map.openDetails')}</Link></div> : null}</> : <div className="rounded-lg border border-dashed border-line bg-surface-base/40 p-4 text-sm text-content-secondary">{t('spatialMetadata.placeholder')}</div>}
            {points.map((point) => (
              <div
                key={point.id}
                className="rounded-lg bg-surface-base/60 p-3 text-sm"
              >
                <p className="font-medium text-content-primary">{point.name}</p>
                <p className="mt-1 text-content-secondary">
                  {point.x != null
                    ? t("spatialMetadata.coordinates", {
                        x: point.x,
                        y: point.y,
                        z: point.z != null ? formatDisplayFloor(point.z) : t('common.unknown'),
                      })
                    : t("spatialMetadata.unresolved")}
                </p>
              </div>
            ))}
            {regions.map((region) => (
              <div
                key={region.id}
                className="rounded-lg bg-surface-base/60 p-3 text-sm"
              >
                <p className="font-medium text-content-primary">
                  {region.name}
                </p>
                <p className="mt-1 text-content-secondary">
                  {region.bounds.min_x != null
                    ? t("spatialMetadata.bounds", region.bounds)
                    : t("spatialMetadata.unresolved")}
                </p>
              </div>
            ))}
            {routes.map((route) => (
              <article
                key={route.id}
                className="rounded-lg bg-surface-base/60 p-3"
              >
                <h3 className="flex items-center gap-2 font-medium text-content-primary">
                  <ListOrdered size={15} />
                  {route.name}
                </h3>
                <p className="mt-1 text-xs text-content-secondary">
                  {t("spatialMetadata.routeEndpoints", {
                    start:
                      route.start_location || t("spatialMetadata.unresolved"),
                    end: route.end_location || t("spatialMetadata.unresolved"),
                  })}
                </p>
                {route.map_images && route.map_images.length > 0 && (
                  <div className="mt-3 flex snap-x gap-2 overflow-x-auto pb-2">
                    {route.map_images.map((source, index) => (
                      <img
                        key={source}
                        src={source}
                        alt={t("spatialMetadata.routeMapAlt", {
                          route: route.name,
                          index: index + 1,
                        })}
                        className="h-44 w-auto max-w-none snap-start rounded-lg bg-surface object-contain"
                        loading="lazy"
                      />
                    ))}
                  </div>
                )}
                {route.steps && route.steps.length > 0 && (
                  <ol className="mt-3 space-y-2">
                    {route.steps.map((step) => (
                      <li
                        key={step.id}
                        className="flex gap-2 text-sm text-content-secondary"
                      >
                        <span className="text-primary">{step.sequence}.</span>
                        <span>
                          {step.instruction ||
                            step.location_name ||
                            t("spatialMetadata.unresolved")}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </article>
            ))}
            {nearbyOrigin && (
              <section>
                <h3 className="flex items-center gap-2 font-semibold">
                  <Radar className="size-4 text-primary" />
                  {t("spatialMetadata.nearby")}
                </h3>
                {nearby.length ? (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {nearby.map((item) => (
                      <a
                        key={item.source_entity_id}
                        href={`/cyclopedia?tab=${item.entity_type === "quest" ? "quests" : item.entity_type === "hunt_zone" ? "zones" : item.entity_type === "item" ? "loot" : item.entity_type === "npc" ? "npcs" : "creatures"}&q=${encodeURIComponent(item.canonical_name)}`}
                        className="rounded-lg bg-surface-base/60 p-3 text-sm"
                      >
                        <strong>{item.canonical_name}</strong>
                        <span className="ml-2 text-xs text-content-muted">
                          {t("spatialMetadata.distance", {
                            distance: Math.round(item.distance),
                          })}
                        </span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-content-muted">
                    {t("spatialMetadata.noNearby")}
                  </p>
                )}
              </section>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
