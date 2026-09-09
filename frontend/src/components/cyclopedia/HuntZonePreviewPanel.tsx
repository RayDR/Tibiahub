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
import type { HuntZone } from '../../types';
import { formatDisplayFloor } from '../../utils/tibiaFloors';

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

  const vocations = useMemo(() => {
    if (!zone) return [];
    if (zone.recommended_vocations?.length) return zone.recommended_vocations;
    return [
      zone.knights_recommended && 'Knight',
      zone.paladins_recommended && 'Paladin',
      zone.sorcerers_recommended && 'Sorcerer',
      zone.druids_recommended && 'Druid',
      zone.monks_recommended && 'Monk',
    ].filter(Boolean) as string[];
  }, [zone]);

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
  const suggestedLevel = zone.recommended_level ?? zone.min_level;
  const place = zone.region || zone.city;
  const hasMap = zone.spatial?.geometry_status === 'mapped' && Boolean(zone.spatial.world_map);
  const experience = zone.avg_exp_hour ? `${zone.avg_exp_hour.toLocaleString()}/h` : zone.exp_rating || '—';
  const profit = zone.avg_profit_hour ? `${zone.avg_profit_hour.toLocaleString()} gp/h` : zone.profit_rating || '—';
  const danger = zone.danger_rating || zone.difficulty || '—';
  const access = zone.access;
  const accessRestricted = access?.status === 'restricted' || zone.access_required === true || zone.requires_quest === true || zone.requires_premium === true;
  const accessPremium = access?.premium_required ?? zone.requires_premium ?? null;
  const accessQuests = access?.quests?.length
    ? access.quests
    : zone.requires_quest && zone.quest_name
      ? [{ id: zone.quest_id, name: zone.quest_name, slug: zone.quest_slug }]
      : [];
  const creatureRows = (zone.creature_spawns || []).filter((spawn) => Boolean(spawn.creature)).slice(0, 5);

  return (
    <article className="creature-preview-panel hunt-zone-preview-panel" data-hunt-zone-preview-panel>
      <section className="creature-preview-identity hunt-zone-preview-identity">
        <div className="hunt-zone-preview-map">
          {hasMap ? (
            <LocalizedMapPreview
              spatial={zone.spatial}
              label={t('huntZoneDetail.mapAlt', { name: zone.name })}
              className="size-full object-cover"
            />
          ) : (
            <div className="grid size-full place-items-center text-primary">
              <BrandCategoryFallbackIcon category="zones" className="size-16 opacity-80" />
            </div>
          )}
        </div>
        <div className="min-w-0">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">{t('nav.zones')}</p>
          <h2 className="creature-preview-name break-words">{zone.name}</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {place ? <span className="creature-preview-chip">{place}</span> : null}
            {zone.spatial?.z != null ? <span className="creature-preview-chip">{t('map.floor', { floor: formatDisplayFloor(zone.spatial.z) })}</span> : null}
            {zone.difficulty ? <span className="creature-preview-chip">{zone.difficulty}</span> : null}
            {accessRestricted ? <span className="creature-preview-chip">{t('huntZoneDetail.access')}</span> : null}
          </div>
          {zone.description ? <p className="mt-3 line-clamp-4 text-sm leading-6 text-content-secondary">{zone.description}</p> : null}
        </div>
      </section>

      <section className="creature-preview-stats" aria-label={t('huntZoneDetail.ratings')}>
        <PreviewStat icon={<Gauge className="size-3.5" />} label={t('huntZoneDetail.levels')} value={suggestedLevel ? `${suggestedLevel}+` : '—'} />
        <PreviewStat icon={<Sparkles className="size-3.5" />} label={t('huntZoneDetail.experience')} value={experience} />
        <PreviewStat icon={<ShieldCheck className="size-3.5" />} label={t('huntZoneDetail.profit')} value={profit} />
      </section>

      <section className="creature-preview-columns hunt-zone-preview-columns">
        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Gauge className="size-4 text-primary" />{t('huntZoneDetail.ratings')}</h3>
          <div className="creature-preview-list">
            <div className="creature-preview-row"><span>{t('huntZoneDetail.danger')}</span><strong className="text-content-primary">{danger}</strong></div>
            <div className="creature-preview-row"><span>{t('huntZoneDetail.party')}</span><strong className="max-w-[10rem] truncate text-content-primary">{zone.recommended_party_size || '—'}</strong></div>
            <div className="creature-preview-row"><span>{t('huntZoneDetail.size')}</span><strong className="text-content-primary">{zone.size || '—'}</strong></div>
          </div>
          {vocations.length ? <div className="mt-3 flex flex-wrap gap-1.5">{vocations.slice(0, 5).map((vocation) => <span key={vocation} className="creature-preview-chip">{vocation}</span>)}</div> : null}
        </div>

        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Crown className="size-4 text-primary" />{t('huntZoneDetail.access')}</h3>
          <div className="creature-preview-list">
            <div className="creature-preview-row"><span>{t('huntZoneDetail.premium')}</span><strong className="text-content-primary">{accessPremium == null ? '—' : accessPremium ? t('common.yes') : t('common.no', { defaultValue: 'No' })}</strong></div>
            <div className="creature-preview-row"><span>{t('huntZoneDetail.minimumLevel', { level: '' }).replace(/[:\s]+$/, '')}</span><strong className="text-content-primary">{access?.minimum_level ?? zone.min_level ?? '—'}</strong></div>
          </div>
          {accessQuests.length ? <div className="mt-3 flex flex-wrap gap-1.5">{accessQuests.slice(0, 3).map((quest) => quest.slug || quest.id ? <Link key={quest.name} to={`/quests/${quest.slug || quest.id}`} className="creature-preview-chip hover:text-primary">{quest.name}</Link> : <span key={quest.name} className="creature-preview-chip">{quest.name}</span>)}</div> : null}
        </div>
      </section>

      <section className="hunt-zone-preview-creatures">
        <div className="flex items-center justify-between gap-3">
          <h3 className="creature-preview-section-title"><Users className="size-4 text-primary" />{t('huntZoneDetail.creatures')}</h3>
          <div className="flex items-center gap-3 text-[10px] font-semibold uppercase tracking-wide text-content-muted">
            <span>{zone.creature_count ?? zone.creature_spawns?.length ?? 0}</span>
            {zone.boss_count != null ? <span className="inline-flex items-center gap-1"><Skull className="size-3" />{zone.boss_count}</span> : null}
          </div>
        </div>
        {creatureRows.length ? (
          <div className="mt-3 grid gap-2">
            {creatureRows.map((spawn) => {
              const creature = spawn.creature!;
              return (
                <Link key={spawn.id} to={`/creatures/${creature.slug || creature.id}`} className="hunt-zone-preview-creature-row">
                  <img src={`/api/v1/creatures/${creature.id}/image?placeholder=false`} alt="" className="size-10 shrink-0 object-contain [image-rendering:pixelated]" />
                  <div className="min-w-0 flex-1"><strong className="block truncate text-sm text-content-primary">{creature.name}</strong>{spawn.quantity ? <span className="text-[11px] text-content-muted">{t('huntZoneDetail.quantity')}: {spawn.quantity}</span> : null}</div>
                  <ArrowRight className="size-3.5 shrink-0 text-content-muted" />
                </Link>
              );
            })}
          </div>
        ) : <p className="mt-3 text-sm text-content-muted">{t('huntZoneDetail.noCreatures')}</p>}
      </section>

      {zone.tips ? (
        <section className="hunt-zone-preview-tips">
          <h3 className="creature-preview-section-title"><Sparkles className="size-4 text-primary" />{t('huntZoneDetail.tips')}</h3>
          <p className="mt-2 line-clamp-5 whitespace-pre-line text-sm leading-6 text-content-secondary">{zone.tips}</p>
        </section>
      ) : null}

      <section className="hunt-zone-preview-actions">
        <Link to={plannerRoute} className="app-button-secondary app-button-sm"><Route className="size-4" />{t('cyclopedia.zones.comparePlanner')}</Link>
        <Link to={route} state={{ from: `${location.pathname}${location.search}` }} className="creature-preview-full-link">
          <MapPin className="size-4" />{t('plannerRecovery.details')}<ArrowRight className="size-4" />
        </Link>
      </section>
    </article>
  );
}

function PreviewStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="creature-preview-stat"><span className="flex items-center gap-1.5">{icon}{label}</span><strong>{value}</strong></div>;
}
