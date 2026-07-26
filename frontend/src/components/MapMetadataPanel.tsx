import { ListOrdered, MapPin, Navigation, Radar } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { spatialApi } from "../services/api";
import type {
  SpatialPointMetadata,
  SpatialRegionMetadata,
  SpatialRouteMetadata,
} from "../types";

export default function MapMetadataPanel({
  entityId,
  locationIdentifier,
}: {
  entityId?: string;
  locationIdentifier?: string;
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

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        if (locationIdentifier) {
          const payload = await spatialApi.forLocation(
            locationIdentifier,
            controller.signal,
          );
          setPoints(payload.points || []);
          setRegions(payload.regions || []);
          const origin = (payload.points || []).find(
            (point: SpatialPointMetadata) =>
              point.x != null && point.y != null && point.z != null,
          );
          if (origin)
            setNearby(
              (
                await spatialApi.nearby(
                  origin.x,
                  origin.y,
                  origin.z,
                  controller.signal,
                )
              ).items || [],
            );
          const details = await Promise.all(
            (payload.routes || [])
              .slice(0, 10)
              .map((route: SpatialRouteMetadata) =>
                spatialApi.route(route.id, controller.signal),
              ),
          );
          setRoutes(details);
        } else if (entityId) {
          const payload = await spatialApi.forEntity(
            entityId,
            controller.signal,
          );
          const entityPoints = (payload.items || []).flatMap(
            (item: { map_point?: SpatialPointMetadata }) =>
              item.map_point ? [item.map_point] : [],
          );
          setPoints(entityPoints);
          setRegions(
            (payload.items || []).flatMap(
              (item: { map_region?: SpatialRegionMetadata }) =>
                item.map_region ? [item.map_region] : [],
            ),
          );
          const origin = entityPoints.find(
            (point: SpatialPointMetadata) =>
              point.x != null && point.y != null && point.z != null,
          );
          if (origin)
            setNearby(
              (
                await spatialApi.nearby(
                  origin.x,
                  origin.y,
                  origin.z,
                  controller.signal,
                )
              ).items || [],
            );
        }
      } catch {
        setPoints([]);
        setRegions([]);
        setRoutes([]);
        setNearby([]);
      } finally {
        setLoaded(true);
      }
    };
    void load();
    return () => controller.abort();
  }, [entityId, locationIdentifier]);

  const nearbyOrigin = points.find(
    (point) => point.x != null && point.y != null && point.z != null,
  );
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
            <div className="grid min-h-36 place-items-center rounded-xl bg-primary-subtle p-4 text-center">
              <Navigation className="size-8 text-primary" />
              <p className="mt-2 text-sm font-semibold">
                {t("spatialMetadata.preview")}
              </p>
              <p className="text-xs text-content-muted">
                {t("spatialMetadata.previewHelp")}
              </p>
            </div>
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
                        z: point.z,
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
                        href={`/cyclopedia?tab=${item.entity_type === "quest" ? "quests" : item.entity_type === "hunt_zone" ? "zones" : item.entity_type === "item" ? "items" : "creatures"}&q=${encodeURIComponent(item.canonical_name)}`}
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
