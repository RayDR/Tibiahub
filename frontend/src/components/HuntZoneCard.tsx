import type { KeyboardEvent, MouseEvent } from 'react';
import { ArrowUpRight, Crown, Gauge, Map, Route, Skull, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { HuntZone } from '../types';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import LocalizedMapPreview from './map/LocalizedMapPreview';
import { useOptionalCyclopediaPreviewSelection } from './cyclopedia/CyclopediaPreviewSelectionContext';
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

const formatCompactMetric = (value?: number | null, suffix = ''): string | null => {
  if (value == null) return null;
  const compact = new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: value >= 1_000_000 ? 1 : 0,
  }).format(value);
  return `${compact}${suffix}`;
};

const levelRangeFor = (zone: HuntZone): string | null => {
  const minimum = zone.min_level && zone.min_level > 0 ? zone.min_level : null;
  const maximum = zone.max_level && zone.max_level > 0 ? zone.max_level : null;
  if (minimum && maximum) return `${minimum}–${maximum}`;
  if (minimum) return `${minimum}+`;
  if (zone.recommended_level && zone.recommended_level > 0) return `${zone.recommended_level}+`;
  return null;
};

const recommendedVocationsFor = (zone: HuntZone): string[] => {
  if (zone.recommended_vocations?.length) return zone.recommended_vocations;
  return [
    zone.knights_recommended && 'Knight',
    zone.paladins_recommended && 'Paladin',
    zone.druids_recommended && 'Druid',
    zone.sorcerers_recommended && 'Sorcerer',
    zone.monks_recommended && 'Monk',
  ].filter(Boolean) as string[];
};

const ratingToneFor = (value?: string | null): 'success' | 'warning' | 'danger' | 'neutral' => {
  const normalized = String(value || '').toLowerCase();
  if (/trivial|easy|low|safe|beginner|excellent/.test(normalized)) return 'success';
  if (/medium|moderate|normal|good|average/.test(normalized)) return 'warning';
  if (/hard|high|danger|extreme|challeng|expert|deadly/.test(normalized)) return 'danger';
  return 'neutral';
};

const placeFor = (zone: HuntZone): string | null => {
  const values = [zone.region, zone.city].filter((value): value is string => Boolean(value?.trim()));
  const unique = values.filter((value, index) => values.findIndex((candidate) => candidate.toLowerCase() === value.toLowerCase()) === index);
  return unique.length ? unique.join(', ') : null;
};

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
  const previewSelection = useOptionalCyclopediaPreviewSelection();
  const identifier = zone.slug || zone.id;
  const identifierString = String(identifier);
  const mapped = zone.spatial?.geometry_status === 'mapped' && Boolean(zone.spatial.world_map);
  const suggestedLevel = zone.recommended_level ?? zone.min_level;
  const levelRange = levelRangeFor(zone);
  const place = placeFor(zone);
  const vocations = recommendedVocationsFor(zone);
  const qualityLabel = zone.danger_rating || zone.difficulty || null;
  const qualityTone = ratingToneFor(qualityLabel);
  const averageExperience = formatCompactMetric(zone.avg_exp_hour, '/h');
  const rawExperienceLabel = rawExperience ? formatCompactMetric(rawExperience) : null;
  const experience = averageExperience || zone.exp_rating || rawExperienceLabel;
  const experienceLabel = zone.avg_exp_hour ? 'XP/h' : 'EXP';
  const averageProfit = formatCompactMetric(zone.avg_profit_hour, ' gp/h');
  const profit = averageProfit || zone.profit_rating;
  const profitLabel = zone.avg_profit_hour ? t('cyclopedia.zones.profitPerHour', { defaultValue: 'Profit/h' }) : t('cyclopedia.zones.profit');
  const isCyclopedia = variant === 'cyclopedia' || Boolean(previewSelection);
  const isSelected = selected || (
    previewSelection?.selection?.kind === 'zone'
    && previewSelection.selection.identifier === identifierString
  );
  const accessRestricted = zone.access?.status === 'restricted' || zone.access_required === true || zone.requires_quest === true || zone.requires_premium === true;
  const selectZone = onSelect || (previewSelection
    ? (candidate: HuntZone) => previewSelection.select({ kind: 'zone', identifier: String(candidate.slug || candidate.id) })
    : undefined);

  const handleCardClick = (event: MouseEvent<HTMLElement>) => {
    if (!isCyclopedia || !selectZone) return;
    const target = event.target;
    if (target instanceof Element && target.closest('a, button, input, select, textarea')) return;
    selectZone(zone);
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!isCyclopedia || !selectZone || (event.key !== 'Enter' && event.key !== ' ')) return;
    const target = event.target;
    if (target instanceof Element && target.closest('a, button, input, select, textarea')) return;
    event.preventDefault();
    selectZone(zone);
  };

  if (isCyclopedia) {
    return (
      <article
        data-hunt-zone-card
        data-cyclopedia-zone-card="true"
        data-zone-identifier={identifierString}
        data-selected={isSelected ? 'true' : 'false'}
        role="button"
        tabIndex={0}
        aria-pressed={isSelected}
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
          <div className="cyclopedia-zone-card-heading">
            <div className="min-w-0 flex-1">
              <h3 className="cyclopedia-zone-card-title">{zone.name}</h3>
              <p className="cyclopedia-zone-card-place">
                {place || t('cyclopedia.zones.notRecorded')}
              </p>
            </div>
            {qualityLabel ? (
              <span className="cyclopedia-zone-rating" data-tone={qualityTone}>{qualityLabel}</span>
            ) : null}
          </div>

          <div className="cyclopedia-zone-card-level-row">
            <strong>{levelRange || '—'}</strong>
            <span>{t('huntZoneDetail.levels')}</span>
          </div>

          {vocations.length ? (
            <div className="cyclopedia-zone-vocations" aria-label={t('huntZoneDetail.vocations')}>
              {vocations.slice(0, 5).map((vocation) => (
                <span key={vocation} title={vocation}>{vocation}</span>
              ))}
            </div>
          ) : null}

          <dl className="cyclopedia-zone-card-kpis">
            <div>
              <dt>{experienceLabel}</dt>
              <dd>{experience || '—'}</dd>
            </div>
            <div>
              <dt>{profitLabel}</dt>
              <dd>{profit || '—'}</dd>
            </div>
          </dl>

          {zone.description ? <p className="cyclopedia-zone-card-description">{zone.description}</p> : null}

          <div className="cyclopedia-zone-card-footer">
            <span><Users className="size-3.5" />{zone.creature_count ?? zone.creature_preview?.length ?? zone.creatures?.length ?? 0}</span>
            {zone.boss_count ? <span><Skull className="size-3.5" />{zone.boss_count}</span> : null}
            {zone.spatial?.z != null ? <span className="cyclopedia-zone-card-floor">{t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) })}</span> : null}
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
