import { ArrowUpRight, Loader2, MapPin } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { spatialApi } from '../../services/api';
import { tibiaMapApi, type WorldMapFloor } from '../../services/tibiaMap';
import type { HuntZoneSpatial, SpatialPointMetadata, SpatialRegionMetadata } from '../../types';
import LocalizedMapPreview from '../map/LocalizedMapPreview';
import { KnowledgeEmpty } from '../knowledge/KnowledgeDetail';
import { formatDisplayFloor } from '../../utils/tibiaFloors';

type MapEvidence = { id: string; label: string; x: number; y: number; z: number; bounds?: HuntZoneSpatial['bounds'] };
const trusted = (value: { confidence: string; verification_state: string }) => {
  if (['rejected', 'unresolved', 'ambiguous'].includes(value.verification_state)) return false;
  return value.verification_state === 'verified' || value.confidence === 'verified' || value.confidence === 'high';
};

export default function QuestMapInsets({ entityId, questName, questSlug }: { entityId?: string; questName: string; questSlug: string }) {
  const { t } = useTranslation();
  const [evidence, setEvidence] = useState<MapEvidence[]>([]);
  const [floors, setFloors] = useState<Record<number, WorldMapFloor | null>>({});
  const [loading, setLoading] = useState(Boolean(entityId));

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setEvidence([]); setFloors({}); setLoading(Boolean(entityId));
    if (!entityId) return () => controller.abort();
    void spatialApi.forEntity(entityId, controller.signal).then(async (payload) => {
      const points = (payload.items || []).flatMap((item: { map_point?: SpatialPointMetadata }) => item.map_point ? [item.map_point] : []).filter(trusted);
      const regions = (payload.items || []).flatMap((item: { map_region?: SpatialRegionMetadata }) => item.map_region ? [item.map_region] : []).filter(trusted);
      const next: MapEvidence[] = [
        ...points.flatMap((point) => point.x != null && point.y != null && point.z != null ? [{ id: point.id, label: point.name, x: point.x, y: point.y, z: point.z }] : []),
        ...regions.flatMap((region) => {
          const { min_x, min_y, max_x, max_y, min_z } = region.bounds;
          return min_x != null && min_y != null && max_x != null && max_y != null && min_z != null
            ? [{ id: region.id, label: region.name, x: (min_x + max_x) / 2, y: (min_y + max_y) / 2, z: min_z, bounds: { min_x, min_y, max_x, max_y } }]
            : [];
        }),
      ].filter((item, index, rows) => rows.findIndex((candidate) => candidate.label === item.label && candidate.x === item.x && candidate.y === item.y && candidate.z === item.z) === index);
      if (!current) return;
      setEvidence(next);
      const bootstraps = await Promise.allSettled([...new Set(next.map((item) => item.z))].map(async (floor) => [floor, (await tibiaMapApi.bootstrap(floor, controller.signal)).world_map] as const));
      if (current) setFloors(Object.fromEntries(bootstraps.flatMap((result) => result.status === 'fulfilled' ? [result.value] : [])));
    }).catch(() => { if (current && !controller.signal.aborted) setEvidence([]); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [entityId]);

  const mapBase = useMemo(() => `/map?q=${encodeURIComponent(questName)}&entityType=quest&slug=${encodeURIComponent(questSlug)}`, [questName, questSlug]);
  if (loading) return <div className="flex min-h-32 items-center justify-center"><Loader2 className="size-5 animate-spin" /></div>;
  if (!evidence.length) return <KnowledgeEmpty>{t('questDetail.noMappedLocations')}</KnowledgeEmpty>;

  return <div className="quest-codex__map-gallery grid gap-3 sm:grid-cols-2">
    {evidence.map((item) => {
      const worldMap = floors[item.z];
      const spatial: HuntZoneSpatial = { geometry_status: 'mapped', geometry_source: 'canonical_spatial_evidence', marker_label: item.label, x: item.x, y: item.y, z: item.z, bounds: item.bounds, world_map: worldMap || null };
      return <article key={item.id} className="quest-codex__map-stamp overflow-hidden rounded-xl border p-2">
        <LocalizedMapPreview spatial={spatial} label={t('questDetail.mapInsetAlt', { location: item.label })} className="aspect-[16/10] rounded-lg" />
        <div className="flex items-center justify-between gap-2 px-1 pb-1 pt-2">
          <div className="min-w-0"><p className="truncate text-sm font-semibold"><MapPin className="mr-1 inline size-3.5" />{item.label}</p><p className="text-xs">{t('map.floor', { floor: formatDisplayFloor(item.z) })}</p></div>
          <Link to={`${mapBase}&floor=${item.z}&location=${encodeURIComponent(item.label)}`} className="app-button-secondary app-button-sm shrink-0" aria-label={t('questDetail.viewAreaOnMap', { location: item.label })}>{t('questDetail.openMap')}<ArrowUpRight className="size-4" /></Link>
        </div>
      </article>;
    })}
  </div>;
}
