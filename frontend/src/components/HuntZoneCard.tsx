import { ArrowUpRight, Crown, Map, Route, Skull, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { HuntZone } from '../types';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import LocalizedMapPreview from './map/LocalizedMapPreview';
import { formatDisplayFloor } from '../utils/tibiaFloors';

interface HuntZoneCardProps {
  zone: HuntZone;
  linkState?: unknown;
  onNavigate?: () => void;
  rawExperience?: number;
  score?: number;
  onInspectMap?: () => void;
  variant?: 'default' | 'cyclopedia';
  selected?: boolean;
  onSelect?: (zone: HuntZone) => void;
}

export default function HuntZoneCard({
  zone,
  linkState,
  onNavigate,
  rawExperience,
  score,
  onInspectMap,
  variant = 'default',
  selected = false,
  onSelect,
}: HuntZoneCardProps) {
  const { t } = useTranslation();
  const identifier = zone.slug || zone.id;
  const mapped = zone.spatial?.geometry_status === 'mapped' && Boolean(zone.spatial.world_map);
  const suggestedLevel = zone.recommended_level ?? zone.min_level;
  const profit = zone.avg_profit_hour ? `${zone.avg_profit_hour.toLocaleString()} gp/h` : zone.profit_rating;
  const experience = zone.avg_exp_hour ? `${zone.avg_exp_hour.toLocaleString()}/h` : rawExperience ? rawExperience.toLocaleString() : zone.exp_rating;
  const place = zone.region || zone.city;
  const isCyclopedia = variant === 'cyclopedia';
  const accessRestricted = zone.access?.status === 'restricted' || zone.access_required === true || zone.requires_quest === true || zone.requires_premium === true;

  const handleCardClick = (event: React.MouseEvent<HTMLElement>) => {
    if (!isCyclopedia || !onSelect) return;
    const target = event.target;
    if (target instanceof Element && target.closest('a, button, input, select, textarea')) return;
    onSelect(zone);
  };

  const handleCardKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (!isCyclopedia || !onSelect || (event.key !== 'Enter' && event.key !== ' ')) return;
    const target = event.target;
    if (target instanceof Element && target.closest('a, button, input, select, textarea')) return;
    event.preventDefault();
    onSelect(zone);
  };

  if (isCyclopedia) {
    return (
      <article
        data-hunt-zone-card
        data-cyclopedia-zone-card="true"
        data-zone-identifier={String(identifier)}
        data-selected={selected ? 'true' : 'false'}
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        onClick={handleCardClick}
        onKeyDown={handleCardKeyDown}
        className="cyclopedia-zone-card group"
      >
        <div className="cyclopedia-zone-card-media">
          {mapped ? (
            <LocalizedMapPreview
              spatial={zone.spatial}
              label={t('huntZoneDetail.mapAlt', { name: zone.name })}
              className="absolute inset-0 size-full transition duration-500 group-hover:scale-[1.025] motion-reduce:transform-none"
            />
          ) : (
            <div className="grid size-full place-items-center text-primary" aria-hidden="true">
              <BrandCategoryFallbackIcon category="zones" className="size-14 opacity-80" />
            </div>
          )}
          <div className="cyclopedia-zone-card-media-scrim" aria-hidden="true" />
          {score != null ? <span className="cyclopedia-zone-score">{Math.round(score)}%</span> : null}
          <Link
            to={`/hunt-zones/${identifier}`}
            state={linkState}
            onClick={onNavigate}
            className="cyclopedia-zone-detail-link"
            aria-label={t('plannerRecovery.details')}
            title={t('plannerRecovery.details')}
          >
            <ArrowUpRight className="size-4" />
          </Link>
        </div>

        <div className="cyclopedia-zone-card-body">
          <div className="min-w-0">
            <h3 className="cyclopedia-zone-card-title">{zone.name}</h3>
            <p className="cyclopedia-zone-card-place">
              {[place, zone.spatial?.z != null ? t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) }) : null]
                .filter(Boolean)
                .join(' · ') || t('cyclopedia.zones.notRecorded')}
            </p>
          </div>

          <dl className="cyclopedia-zone-card-stats">
            <div><dt>{t('cyclopedia.zones.suggested')}</dt><dd>{suggestedLevel ? t('cyclopedia.zones.level', { level: suggestedLevel }) : '—'}</dd></div>
            <div><dt>EXP</dt><dd>{experience || '—'}</dd></div>
            <div><dt>{t('cyclopedia.zones.profit')}</dt><dd>{profit || '—'}</dd></div>
            <div><dt>{t('cyclopedia.zones.danger')}</dt><dd>{zone.danger_rating || zone.difficulty || '—'}</dd></div>
          </dl>

          <div className="cyclopedia-zone-card-footer">
            <span><Users className="size-3.5" />{zone.creature_count ?? zone.creature_preview?.length ?? zone.creatures?.length ?? 0}</span>
            <span><Skull className="size-3.5" />{zone.boss_count ?? 0}</span>
            {accessRestricted ? <span className="cyclopedia-zone-access"><Crown className="size-3.5" />{t('huntZoneDetail.access')}</span> : null}
          </div>
        </div>
      </article>
    );
  }

  return <article data-hunt-zone-card className="group flex min-h-[22rem] flex-col overflow-hidden rounded-2xl border border-line bg-surface-raised shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-xl motion-reduce:transform-none">
    {mapped ? (
      <div className="relative h-36 w-full shrink-0 overflow-hidden border-b border-line bg-surface-base">
        <LocalizedMapPreview
          spatial={zone.spatial}
          label={t('huntZoneDetail.mapAlt', { name: zone.name })}
          className="absolute inset-0 size-full transition duration-500 group-hover:scale-[1.03] motion-reduce:transform-none"
        />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-surface-raised/35" />
      </div>
    ) : (
      <div className="grid h-28 w-full shrink-0 place-items-center border-b border-line bg-surface-base/55 text-primary" aria-hidden="true">
        <BrandCategoryFallbackIcon category="zones" className="size-12 opacity-80" />
      </div>
    )}

    <div className="flex min-w-0 flex-1 flex-col p-4 text-content-primary sm:p-5">
      {score != null ? (
        <div className="flex justify-end">
          <span className="rounded-lg bg-primary px-2 py-1 text-xs font-bold text-content-on-primary">{Math.round(score)}%</span>
        </div>
      ) : null}

      <div className="mt-auto">
        <div className="min-h-[4.25rem]">
          <Link to={`/hunt-zones/${identifier}`} state={linkState} onClick={onNavigate} className="line-clamp-2 font-serif text-xl font-bold leading-tight text-content-primary hover:text-primary sm:text-2xl">{zone.name}</Link>
          <p className="mt-1 min-h-5 truncate text-sm text-content-secondary">{[place, zone.spatial?.z != null ? t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) }) : null].filter(Boolean).join(' · ')}</p>
        </div>

        <div className="mt-3 grid min-h-[3.25rem] grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <p className="truncate text-content-secondary"><span className="block text-[10px] uppercase tracking-wide text-content-muted">{t('cyclopedia.zones.suggested')}</span><strong className="text-content-primary">{suggestedLevel ? t('cyclopedia.zones.level', { level: suggestedLevel }) : t('cyclopedia.zones.needsAnalysis')}</strong></p>
          <p className="truncate text-content-secondary"><span className="block text-[10px] uppercase tracking-wide text-content-muted">{t('cyclopedia.zones.danger')}</span><strong className="text-content-primary">{zone.danger_rating || zone.difficulty || t('cyclopedia.zones.notRecorded')}</strong></p>
          <p className="truncate text-content-secondary"><span className="block text-[10px] uppercase tracking-wide text-content-muted">EXP</span><strong className="text-content-primary">{experience || t('cyclopedia.zones.notRecorded')}</strong></p>
          <p className="truncate text-content-secondary"><span className="block text-[10px] uppercase tracking-wide text-content-muted">{t('cyclopedia.zones.profit')}</span><strong className="text-content-primary">{profit || t('cyclopedia.zones.notRecorded')}</strong></p>
        </div>

        <div className="mt-4 grid w-full grid-cols-2 gap-2">
          <Link to={`/planner?zone=${encodeURIComponent(String(identifier))}`} className="inline-flex min-h-9 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-line bg-surface-overlay/65 px-2 text-center text-xs font-semibold leading-tight text-content-primary backdrop-blur hover:bg-surface-overlay/90"><Route size={14} className="shrink-0" />{t('cyclopedia.zones.comparePlanner')}</Link>
          {onInspectMap ? <button type="button" onClick={onInspectMap} className="inline-flex min-h-9 min-w-0 items-center justify-center gap-1.5 rounded-lg bg-primary px-2 text-center text-xs font-semibold leading-tight text-content-on-primary hover:bg-primary-hover"><Map size={14} className="shrink-0" />{t('plannerRecovery.inspect')}</button> : <Link to={`/hunt-zones/${identifier}`} state={linkState} onClick={onNavigate} className="inline-flex min-h-9 min-w-0 items-center justify-center gap-1.5 rounded-lg bg-primary px-2 text-center text-xs font-semibold leading-tight text-content-on-primary hover:bg-primary-hover">{t('plannerRecovery.details')}<ArrowUpRight size={14} className="shrink-0" /></Link>}
        </div>
      </div>
    </div>
  </article>;
}
