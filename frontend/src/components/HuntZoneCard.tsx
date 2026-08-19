import { ArrowUpRight, Map, MapPinOff, Route } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { HuntZone } from '../types';
import LocalizedMapPreview from './map/LocalizedMapPreview';
import { formatDisplayFloor } from '../utils/tibiaFloors';

interface HuntZoneCardProps {
  zone: HuntZone;
  linkState?: unknown;
  onNavigate?: () => void;
  rawExperience?: number;
  score?: number;
  onInspectMap?: () => void;
}

export default function HuntZoneCard({ zone, linkState, onNavigate, rawExperience, score, onInspectMap }: HuntZoneCardProps) {
  const { t } = useTranslation();
  const identifier = zone.slug || zone.id;
  const mapped = zone.spatial?.geometry_status === 'mapped' && Boolean(zone.spatial.world_map);
  const suggestedLevel = zone.recommended_level ?? zone.min_level;
  const profit = zone.avg_profit_hour ? `${zone.avg_profit_hour.toLocaleString()} gp/h` : zone.profit_rating;
  const experience = zone.avg_exp_hour ? `${zone.avg_exp_hour.toLocaleString()}/h` : rawExperience ? rawExperience.toLocaleString() : zone.exp_rating;
  const place = zone.region || zone.city;

  return <article data-hunt-zone-card className="group relative isolate flex min-h-[21rem] overflow-hidden rounded-2xl border border-line bg-surface-raised shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-xl motion-reduce:transform-none">
    <LocalizedMapPreview spatial={zone.spatial} label={t('huntZoneDetail.mapAlt', { name: zone.name })} className="absolute inset-0 size-full transition duration-500 group-hover:scale-[1.03] motion-reduce:transform-none" />
    <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/55 to-black/95" />
    <div className="relative flex min-w-0 flex-1 flex-col p-4 text-white sm:p-5">
      <div className="flex min-h-7 items-start justify-between gap-3">
        {mapped ? <span className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-black/45 px-2 py-1 text-[11px] font-semibold backdrop-blur"><Map size={12} />{t('map.mapped')}</span> : <span className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-black/50 px-2 py-1 text-[11px] text-white/75 backdrop-blur"><MapPinOff size={12} />{t('map.locationNotMapped')}</span>}
        {score != null ? <span className="rounded-lg bg-primary px-2 py-1 text-xs font-bold text-content-on-primary">{Math.round(score)}%</span> : null}
      </div>

      <div className="mt-auto pt-16">
        <div className="min-h-[4.25rem]">
          <Link to={`/hunt-zones/${identifier}`} state={linkState} onClick={onNavigate} className="line-clamp-2 font-serif text-xl font-bold leading-tight text-white hover:text-primary-light sm:text-2xl">{zone.name}</Link>
          <p className="mt-1 min-h-5 truncate text-sm text-white/75">{[place, zone.spatial?.z != null ? t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) }) : null].filter(Boolean).join(' · ') || t('map.locationNotMapped')}</p>
        </div>

        <div className="mt-3 grid min-h-[3.25rem] grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <p className="truncate text-white/70"><span className="block text-[10px] uppercase tracking-wide text-white/45">{t('cyclopedia.zones.suggested')}</span><strong className="text-white">{suggestedLevel ? t('cyclopedia.zones.level', { level: suggestedLevel }) : t('cyclopedia.zones.needsAnalysis')}</strong></p>
          <p className="truncate text-white/70"><span className="block text-[10px] uppercase tracking-wide text-white/45">{t('cyclopedia.zones.danger')}</span><strong className="text-white">{zone.danger_rating || zone.difficulty || t('cyclopedia.zones.notRecorded')}</strong></p>
          <p className="truncate text-white/70"><span className="block text-[10px] uppercase tracking-wide text-white/45">EXP</span><strong className="text-white">{experience || t('cyclopedia.zones.notRecorded')}</strong></p>
          <p className="truncate text-white/70"><span className="block text-[10px] uppercase tracking-wide text-white/45">{t('cyclopedia.zones.profit')}</span><strong className="text-white">{profit || t('cyclopedia.zones.notRecorded')}</strong></p>
        </div>

        <div className="mt-4 grid min-h-9 grid-cols-2 gap-2">
          <Link to={`/planner?zone=${encodeURIComponent(String(identifier))}`} className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-white/25 bg-black/35 px-3 text-xs font-semibold text-white backdrop-blur hover:bg-black/55"><Route size={14} />{t('cyclopedia.zones.comparePlanner')}</Link>
          {onInspectMap ? <button type="button" onClick={onInspectMap} className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-content-on-primary hover:bg-primary-hover"><Map size={14} />{t('plannerRecovery.inspect')}</button> : <Link to={`/hunt-zones/${identifier}`} state={linkState} onClick={onNavigate} className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-content-on-primary hover:bg-primary-hover">{t('plannerRecovery.details')}<ArrowUpRight size={14} /></Link>}
        </div>
      </div>
    </div>
  </article>;
}
