import { lazy, Suspense, useEffect, useState } from 'react';
import { Compass, Crown, Gauge, Loader2, MapPin, Sparkles, Users } from 'lucide-react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { KnowledgeBackLink, KnowledgeBadge, KnowledgeEmpty, KnowledgeFact, KnowledgeFacts, KnowledgeHero, KnowledgeSection } from '../components/knowledge/KnowledgeDetail';
import KnowledgeCategoryIcon from '../components/knowledge/KnowledgeCategoryIcon';
import { Page } from '../components/ui';
import { huntZonesApi } from '../services/api';
import type { HuntZone } from '../types';
import { SuggestCorrectionLink } from '../components/feedback/GitHubFeedbackLink';
import { useSeoMetadata } from '../utils/seo';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));

export default function HuntZoneDetailPage() {
  const { identifier } = useParams<{ identifier: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [zone, setZone] = useState<HuntZone | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useSeoMetadata(zone ? {
    title: `${zone.name} — Tibia hunt zone`,
    description: zone.description || `Levels, creatures, access and hunting information for ${zone.name}.`,
    canonicalPath: `/hunt-zones/${zone.slug || zone.id}`,
    type: 'article', image: huntZonesApi.getMapImageUrl(zone.id, false),
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }, { name: zone.name, path: `/hunt-zones/${zone.slug || zone.id}` }],
  } : null);

  useEffect(() => {
    if (!identifier) return undefined;
    const controller = new AbortController();
    setLoading(true);
    void huntZonesApi.getByIdentifier(identifier, controller.signal).then((result) => {
      setZone(result);
      setError(false);
      if (result.slug && result.slug !== identifier) navigate(`/hunt-zones/${result.slug}`, { replace: true, state: location.state });
    }).catch(() => setError(true)).finally(() => setLoading(false));
    return () => controller.abort();
  }, [identifier, location.state, navigate]);

  if (loading) return <Page><div className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /></div></Page>;
  if (!zone || error) return <Page><div className="rounded-2xl border border-danger/25 bg-danger-subtle p-6 text-danger"><h1 className="text-xl font-bold">{t('huntZoneDetail.unavailable')}</h1><p className="mt-2">{t('huntZoneDetail.notFound')}</p></div></Page>;

  const back = (location.state as { from?: string } | null)?.from || '/cyclopedia?tab=zones';
  const levelRange = zone.min_level > 0 ? (zone.max_level ? `${zone.min_level}–${zone.max_level}` : `${zone.min_level}+`) : null;
  const vocations = zone.recommended_vocations?.length ? zone.recommended_vocations : [zone.knights_recommended && 'Knight', zone.paladins_recommended && 'Paladin', zone.sorcerers_recommended && 'Sorcerer', zone.druids_recommended && 'Druid', zone.monks_recommended && 'Monk'].filter(Boolean) as string[];
  const quickFacts = [
    levelRange ? <KnowledgeFact key="levels" label={t('huntZoneDetail.levels')} value={levelRange} /> : null,
    vocations.length ? <KnowledgeFact key="vocations" label={t('huntZoneDetail.vocations')} value={vocations.join(', ')} /> : null,
    zone.recommended_party_size ? <KnowledgeFact key="party" label={t('huntZoneDetail.party')} value={zone.recommended_party_size} /> : null,
    zone.size ? <KnowledgeFact key="size" label={t('huntZoneDetail.size')} value={zone.size} /> : null,
  ].filter(Boolean);
  const ratingFacts = [
    zone.avg_exp_hour || zone.exp_rating ? <KnowledgeFact key="experience" label={t('huntZoneDetail.experience')} value={zone.avg_exp_hour ? `${zone.avg_exp_hour.toLocaleString()}/h` : zone.exp_rating} /> : null,
    zone.avg_profit_hour || zone.profit_rating ? <KnowledgeFact key="profit" label={t('huntZoneDetail.profit')} value={zone.avg_profit_hour ? `${zone.avg_profit_hour.toLocaleString()} gp/h` : zone.profit_rating} /> : null,
    zone.danger_rating || zone.difficulty ? <KnowledgeFact key="danger" label={t('huntZoneDetail.danger')} value={zone.danger_rating || zone.difficulty} /> : null,
  ].filter(Boolean);
  const mapFloor = zone.location_z ?? zone.map_z;

  return <Page>
    <KnowledgeBackLink to={back}>{t('huntZoneDetail.back')}</KnowledgeBackLink>
    <KnowledgeHero
      eyebrow={t('huntZoneDetail.eyebrow')}
      title={zone.name}
      description={zone.description || undefined}
      media={<div className="grid aspect-[4/3] place-items-center rounded-2xl border border-line bg-surface-base"><KnowledgeCategoryIcon category="zones" label={t('nav.zones')} className="size-28" mediaClassName="size-24" /></div>}
      badges={<>{zone.city ? <KnowledgeBadge tone="primary">{zone.city}</KnowledgeBadge> : null}{zone.region && zone.region !== zone.city ? <KnowledgeBadge>{zone.region}</KnowledgeBadge> : null}{zone.difficulty ? <KnowledgeBadge>{zone.difficulty}</KnowledgeBadge> : null}{zone.requires_premium ? <KnowledgeBadge tone="warning">{t('huntZoneDetail.premium')}</KnowledgeBadge> : null}<a href="#hunt-zone-map" className="app-button-secondary app-button-sm"><Compass size={15} />{t('huntZoneDetail.viewMap')}</a><Link to={`/map?entityType=hunt_zone&slug=${encodeURIComponent(zone.slug || zone.name)}&q=${encodeURIComponent(zone.name)}`} className="app-button-primary app-button-sm"><MapPin size={15} />{t('map.openDetails')}</Link></>}
    />

    {quickFacts.length ? <div className="mt-6"><KnowledgeFacts>{quickFacts}</KnowledgeFacts></div> : null}

    <div className="mt-8 space-y-6">
      <KnowledgeSection id="hunt-zone-map" title={t('huntZoneDetail.map')} icon={<MapPin size={20} />}>
        {(zone.city || zone.region) ? <p className="mb-3 text-sm text-content-secondary">{[zone.city, zone.region].filter((value, index, rows) => value && rows.indexOf(value) === index).join(' · ')}</p> : null}
        <Suspense fallback={<div className="grid min-h-56 place-items-center rounded-xl border border-line bg-surface-base/60 text-sm text-content-muted">{t('common.loading')}</div>}>
          <TibiaMapViewer
            imageUrl={huntZonesApi.getMapImageUrl(zone.id, false)}
            label={t('huntZoneDetail.mapAlt', { name: zone.name })}
            floor={mapFloor}
            floorLabel={mapFloor != null ? t('huntZoneDetail.floor', { floor: mapFloor }) : undefined}
            mapBounds={zone.map_bounds}
            center={zone.location_x != null && zone.location_y != null ? { x: zone.location_x, y: zone.location_y } : undefined}
            emptyMessage={t('huntZoneDetail.mapEmpty')}
            resetLabel={t('huntZoneDetail.resetMap')}
            zoomInLabel={t('huntZoneDetail.zoomIn')}
            zoomOutLabel={t('huntZoneDetail.zoomOut')}
          />
        </Suspense>
        {zone.location_x != null && zone.location_y != null ? <p className="mt-3 text-xs text-content-muted">{t('huntZoneDetail.coordinates', { x: zone.location_x, y: zone.location_y, z: zone.location_z ?? '—' })}</p> : null}
        <p className="mt-2 text-xs text-content-muted">{t('huntZoneDetail.mapContext')}</p>
      </KnowledgeSection>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(18rem,1fr)]">
        <div className="space-y-6">
          {ratingFacts.length ? <KnowledgeSection title={t('huntZoneDetail.ratings')} icon={<Gauge size={20} />}><KnowledgeFacts>{ratingFacts}</KnowledgeFacts></KnowledgeSection> : null}
          <KnowledgeSection title={t('huntZoneDetail.creatures')} icon={<Users size={20} />}>{zone.creature_spawns?.length ? <div className="grid gap-3 sm:grid-cols-2">{zone.creature_spawns.map((spawn) => spawn.creature ? <Link key={spawn.id} to={`/creatures/${spawn.creature.slug || spawn.creature.id}`} className="group flex min-h-20 items-center gap-3 rounded-xl border border-line bg-surface-base/60 p-3 hover:border-primary"><img src={`/api/v1/creatures/${spawn.creature.id}/image?placeholder=false`} alt="" className="size-14 shrink-0 object-contain [image-rendering:pixelated]" /><div><h3 className="font-semibold text-content-primary group-hover:text-primary">{spawn.creature.name}</h3>{spawn.quantity ? <p className="text-xs text-content-secondary">{t('huntZoneDetail.quantity')}: {spawn.quantity}</p> : null}{spawn.notes ? <p className="mt-1 text-xs text-content-muted">{spawn.notes}</p> : null}</div></Link> : null)}</div> : <KnowledgeEmpty>{t('huntZoneDetail.noCreatures')}</KnowledgeEmpty>}</KnowledgeSection>
          {zone.tips ? <KnowledgeSection title={t('huntZoneDetail.tips')} icon={<Sparkles size={20} />}><p className="whitespace-pre-line leading-7 text-content-secondary">{zone.tips}</p></KnowledgeSection> : null}
        </div>
        <div className="space-y-6">
          <KnowledgeSection title={t('huntZoneDetail.access')} icon={<Crown size={20} />}><div className="space-y-3 text-sm text-content-secondary">{!zone.requires_premium && !zone.requires_quest ? <p>{t('huntZoneDetail.accessClear')}</p> : null}{zone.requires_premium ? <p>{t('huntZoneDetail.premiumRequired')}</p> : null}{zone.requires_quest ? zone.quest_name ? <p>{t('huntZoneDetail.requires')} {zone.quest_slug || zone.quest_id ? <Link className="font-semibold text-primary hover:underline" to={`/quests/${zone.quest_slug || zone.quest_id}`}>{zone.quest_name}</Link> : <span className="font-semibold text-content-primary">{zone.quest_name}</span>}</p> : <p>{t('huntZoneDetail.questUnresolved')}</p> : null}</div></KnowledgeSection>
        </div>
      </div>
    </div>
    <div className="mt-6 flex justify-end"><SuggestCorrectionLink entityType="Hunt zone" entityName={zone.name} /></div>
  </Page>;
}
