import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowRight,
  Crown,
  Gauge,
  Loader2,
  MapPin,
  Route,
  ShieldCheck,
  Sparkles,
  Skull,
  Users,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import BrandCategoryFallbackIcon from '../icons/BrandCategoryFallbackIcon';
import LocalizedMapPreview from '../map/LocalizedMapPreview';
import { huntZonesApi } from '../../services/api';
import { buildMapEntityUrl } from '../../services/tibiaMap';
import type { HuntZone } from '../../types';
import { formatDisplayFloor } from '../../utils/tibiaFloors';

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

const placeFor = (zone: HuntZone): string | null => {
  const values = [zone.region, zone.city].filter((value): value is string => Boolean(value?.trim()));
  const unique = values.filter((value, index) => values.findIndex((candidate) => candidate.toLowerCase() === value.toLowerCase()) === index);
  return unique.length ? unique.join(', ') : null;
};

const riskLevelFor = (value?: string | null): number | null => {
  const normalized = String(value || '').toLowerCase();
  if (!normalized) return null;
  if (/trivial|very low|safe|beginner/.test(normalized)) return 1;
  if (/easy|low/.test(normalized)) return 2;
  if (/medium|moderate|normal|average|good/.test(normalized)) return 3;
  if (/hard|high|danger|extreme|challeng|expert|deadly/.test(normalized)) return 4;
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

export default function HuntZonePreviewPanel({ identifier }: { identifier: string }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [zone, setZone] = useState<HuntZone | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setZone(null);
    setLoading(true);
    setError(false);

    void huntZonesApi
      .getByIdentifier(identifier, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setZone(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [identifier]);

  const vocations = useMemo(() => zone ? recommendedVocationsFor(zone) : [], [zone]);

  if (loading) {
    return (
      <div className="creature-preview-panel hunt-zone-preview-panel creature-preview-loading" role="status">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span className="text-sm text-content-muted">{t('common.loading')}</span>
      </div>
    );
  }

  if (!zone || error) {
    return <div className="creature-preview-panel hunt-zone-preview-panel p-5 text-sm text-danger">{t('huntZoneDetail.unavailable')}</div>;
  }

  const route = `/hunt-zones/${zone.slug || zone.id}`;
  const plannerRoute = `/planner?zone=${encodeURIComponent(String(zone.slug || zone.id))}`;
  const mapRoute = buildMapEntityUrl({
    canonicalEntityId: zone.knowledge_entity_id,
    entityType: 'hunt_zone',
    name: zone.name,
    slug: zone.slug || String(zone.id),
    floor: zone.spatial?.z,
  });
  const levelRange = levelRangeFor(zone);
  const place = placeFor(zone);
  const hasMap = zone.spatial?.geometry_status === 'mapped' && Boolean(zone.spatial.world_map);
  const experience = formatCompactMetric(zone.avg_exp_hour, '/h') || zone.exp_rating || '—';
  const profit = formatCompactMetric(zone.avg_profit_hour, ' gp/h') || zone.profit_rating || '—';
  const danger = zone.danger_rating || zone.difficulty || null;
  const dangerLevel = riskLevelFor(danger);
  const access = zone.access;
  const accessRestricted = access?.status === 'restricted' || zone.access_required === true || zone.requires_quest === true || zone.requires_premium === true;
  const accessPremium = access?.premium_required ?? zone.requires_premium ?? null;
  const accessQuests = access?.quests?.length
    ? access.quests
    : zone.requires_quest && zone.quest_name
      ? [{ id: zone.quest_id, name: zone.quest_name, slug: zone.quest_slug }]
      : [];
  const creatureRows = (zone.creature_spawns || []).filter((spawn) => Boolean(spawn.creature)).slice(0, 5);
  const displayId = zone.external_id || zone.id;

  return (
    <article className="creature-preview-panel hunt-zone-preview-panel" data-hunt-zone-preview-panel>
      <section className="creature-preview-identity hunt-zone-preview-identity">
        <div className="hunt-zone-preview-thumb">
          {hasMap ? (
            <LocalizedMapPreview
              spatial={zone.spatial}
              label={t('huntZoneDetail.mapAlt', { name: zone.name })}
              className="size-full object-cover"
            />
          ) : (
            <div className="grid size-full place-items-center text-primary">
              <BrandCategoryFallbackIcon category="zones" className="size-14 opacity-80" />
            </div>
          )}
        </div>

        <div className="min-w-0">
          <div className="hunt-zone-preview-title-row">
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">{t('nav.zones')}</p>
              <h2 className="creature-preview-name break-words">{zone.name}</h2>
            </div>
            <span className="hunt-zone-preview-id">#{displayId}</span>
          </div>

          {place ? <p className="mt-1 truncate text-xs text-content-muted">{place}</p> : null}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {danger ? <span className="creature-preview-chip hunt-zone-preview-rating">{danger}</span> : null}
            {levelRange ? <span className="creature-preview-chip">{levelRange}</span> : null}
            {zone.spatial?.z != null ? <span className="creature-preview-chip">{t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) })}</span> : null}
            {accessRestricted ? <span className="creature-preview-chip">{t('huntZoneDetail.access')}</span> : null}
          </div>
        </div>
      </section>

      <section className="hunt-zone-preview-map-stage">
        {hasMap ? (
          <LocalizedMapPreview
            spatial={zone.spatial}
            label={t('huntZoneDetail.mapAlt', { name: zone.name })}
            className="size-full object-cover"
          />
        ) : (
          <div className="grid size-full place-items-center gap-2 text-center text-content-muted">
            <BrandCategoryFallbackIcon category="zones" className="size-14 text-primary opacity-70" />
            <span className="text-xs">{t('map.locationNotMapped')}</span>
          </div>
        )}
      </section>

      <section className="creature-preview-stats hunt-zone-preview-kpis" aria-label={t('huntZoneDetail.ratings')}>
        <PreviewStat icon={<Sparkles className="size-3.5" />} label={zone.avg_exp_hour ? 'XP/h' : t('huntZoneDetail.experience')} value={experience} />
        <PreviewStat icon={<ShieldCheck className="size-3.5" />} label={zone.avg_profit_hour ? t('cyclopedia.zones.profitPerHour', { defaultValue: 'Profit/h' }) : t('huntZoneDetail.profit')} value={profit} />
        <PreviewStat icon={<Users className="size-3.5" />} label={t('huntZoneDetail.party')} value={zone.recommended_party_size || '—'} />
      </section>

      <section className="creature-preview-columns hunt-zone-preview-columns hunt-zone-preview-profile-grid">
        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Users className="size-4 text-primary" />{t('huntZoneDetail.vocations')}</h3>
          {vocations.length ? (
            <div className="hunt-zone-preview-vocations">
              {vocations.slice(0, 5).map((vocation) => <span key={vocation}>{vocation}</span>)}
            </div>
          ) : (
            <p className="mt-3 text-xs text-content-muted">{t('cyclopedia.zones.notRecorded')}</p>
          )}
          {levelRange ? (
            <p className="mt-3 text-xs text-content-secondary">
              <span className="text-content-muted">{t('huntZoneDetail.levels')}:</span> {levelRange}
            </p>
          ) : null}
        </div>

        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Gauge className="size-4 text-primary" />{t('cyclopedia.zones.danger')}</h3>
          <div className="hunt-zone-preview-risk-list">
            <RiskRow label={t('huntZoneDetail.danger')} value={danger || '—'} level={dangerLevel} />
            <RiskRow label={t('huntZoneDetail.size')} value={zone.size || '—'} />
            <RiskRow label={t('huntZoneDetail.access')} value={accessRestricted ? t('huntZoneDetail.access') : access?.status === 'documented' ? t('common.yes') : '—'} />
          </div>
        </div>
      </section>

      <section className="creature-preview-columns hunt-zone-preview-columns hunt-zone-preview-detail-grid">
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <h3 className="creature-preview-section-title"><Users className="size-4 text-primary" />{t('huntZoneDetail.creatures')}</h3>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-content-muted">
              <span>{zone.creature_count ?? zone.creature_spawns?.length ?? 0}</span>
              {zone.boss_count != null ? <span className="inline-flex items-center gap-1"><Skull className="size-3" />{zone.boss_count}</span> : null}
            </div>
          </div>

          {creatureRows.length ? (
            <div className="mt-3 grid gap-1.5">
              {creatureRows.map((spawn) => {
                const creature = spawn.creature!;
                return (
                  <Link key={spawn.id} to={`/creatures/${creature.slug || creature.id}`} className="hunt-zone-preview-creature-row">
                    <img src={`/api/v1/creatures/${creature.id}/image?placeholder=false`} alt="" className="size-8 shrink-0 object-contain [image-rendering:pixelated]" />
                    <div className="min-w-0 flex-1">
                      <strong className="block truncate text-xs text-content-primary">{creature.name}</strong>
                      {spawn.quantity ? <span className="text-[10px] text-content-muted">{spawn.quantity}</span> : null}
                    </div>
                    <ArrowRight className="size-3 shrink-0 text-content-muted" />
                  </Link>
                );
              })}
            </div>
          ) : <p className="mt-3 text-xs text-content-muted">{t('huntZoneDetail.noCreatures')}</p>}
        </div>

        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><MapPin className="size-4 text-primary" />{t('huntZoneDetail.map')}</h3>
          <div className="creature-preview-list hunt-zone-preview-location-list">
            {zone.region ? <div className="creature-preview-row"><span>{t('huntZoneDetail.region', { defaultValue: 'Region' })}</span><strong>{zone.region}</strong></div> : null}
            {zone.city ? <div className="creature-preview-row"><span>{t('huntZoneDetail.city', { defaultValue: 'City' })}</span><strong>{zone.city}</strong></div> : null}
            {zone.spatial?.z != null ? <div className="creature-preview-row"><span>{t('map.floor', { floor: '' }).replace(/[:\s]+$/, '')}</span><strong>{formatDisplayFloor(zone.spatial.z)}</strong></div> : null}
            {zone.spatial?.x != null && zone.spatial?.y != null ? <div className="creature-preview-row"><span>{t('huntZoneDetail.coordinates', { x: '', y: '', z: '' }).split(':')[0]}</span><strong>{Math.round(zone.spatial.x)}, {Math.round(zone.spatial.y)}</strong></div> : null}
          </div>

          <div className="mt-4">
            <h3 className="creature-preview-section-title"><Crown className="size-4 text-primary" />{t('huntZoneDetail.access')}</h3>
            <div className="creature-preview-list">
              <div className="creature-preview-row"><span>{t('huntZoneDetail.premium')}</span><strong>{accessPremium == null ? '—' : accessPremium ? t('common.yes') : t('common.no', { defaultValue: 'No' })}</strong></div>
              {access?.minimum_level || zone.min_level ? <div className="creature-preview-row"><span>{t('huntZoneDetail.minimumLevel', { level: '' }).replace(/[:\s]+$/, '')}</span><strong>{access?.minimum_level ?? zone.min_level}</strong></div> : null}
            </div>
            {accessQuests.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {accessQuests.slice(0, 3).map((quest) => quest.slug || quest.id
                  ? <Link key={quest.name} to={`/quests/${quest.slug || quest.id}`} className="creature-preview-chip hover:text-primary">{quest.name}</Link>
                  : <span key={quest.name} className="creature-preview-chip">{quest.name}</span>)}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      {zone.description || zone.tips || access?.notes ? (
        <section className="hunt-zone-preview-tips">
          <h3 className="creature-preview-section-title"><Sparkles className="size-4 text-primary" />{t('huntZoneDetail.tips')}</h3>
          <p className="mt-2 line-clamp-6 whitespace-pre-line text-sm leading-6 text-content-secondary">
            {zone.tips || zone.description || access?.notes}
          </p>
        </section>
      ) : null}

      <section className="hunt-zone-preview-actions">
        {hasMap ? (
          <Link to={mapRoute} className="hunt-zone-preview-primary-action">
            <MapPin className="size-4" />{t('huntZoneDetail.viewMap')}<ArrowRight className="size-4" />
          </Link>
        ) : (
          <Link to={route} state={{ from: `${location.pathname}${location.search}` }} className="hunt-zone-preview-primary-action">
            <MapPin className="size-4" />{t('plannerRecovery.details')}<ArrowRight className="size-4" />
          </Link>
        )}
        <Link to={plannerRoute} className="hunt-zone-preview-secondary-action"><Route className="size-4" />{t('cyclopedia.zones.comparePlanner')}</Link>
      </section>
    </article>
  );
}

function PreviewStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="creature-preview-stat"><span className="flex items-center gap-1.5">{icon}{label}</span><strong>{value}</strong></div>;
}

function RiskRow({ label, value, level }: { label: string; value: string; level?: number | null }) {
  return (
    <div className="hunt-zone-preview-risk-row">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span>{label}</span>
        <strong className="truncate">{value}</strong>
      </div>
      {level ? (
        <span className="hunt-zone-preview-risk-meter" aria-hidden="true">
          {[1, 2, 3, 4].map((segment) => <i key={segment} data-active={segment <= level ? 'true' : 'false'} />)}
        </span>
      ) : null}
    </div>
  );
}
