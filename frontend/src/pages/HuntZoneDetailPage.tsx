import { lazy, Suspense, useEffect, useState } from 'react';
import { Crown, Gauge, Loader2, MapPinned, Sparkles, Users } from 'lucide-react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { KnowledgeBackLink, KnowledgeBadge, KnowledgeEmpty, KnowledgeFact, KnowledgeFacts, KnowledgeHero, KnowledgeSection } from '../components/knowledge/KnowledgeDetail';
import KnowledgeCategoryIcon from '../components/knowledge/KnowledgeCategoryIcon';
import { Page } from '../components/ui';
import { huntZonesApi } from '../services/api';
import type { HuntZone } from '../types';
import { SuggestCorrectionLink } from '../components/feedback/GitHubFeedbackLink';
import { useSeoMetadata } from '../utils/seo';
import LocalizedMapPreview from '../components/map/LocalizedMapPreview';
import { tibiaMapApi, type HuntZoneMapContext } from '../services/tibiaMap';
import { formatDisplayFloor } from '../utils/tibiaFloors';

const TibiaMapViewer = lazy(() => import('../components/map/TibiaMapViewer'));

export default function HuntZoneDetailPage() {
  const { identifier } = useParams<{ identifier: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [zone, setZone] = useState<HuntZone | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mapContext, setMapContext] = useState<HuntZoneMapContext | null>(null);

  useSeoMetadata(zone ? {
    title: `${zone.name} — Tibia hunt zone`,
    description: zone.description || `Levels, creatures, access and hunting information for ${zone.name}.`,
    canonicalPath: `/hunt-zones/${zone.slug || zone.id}`,
    type: 'article',
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }, { name: zone.name, path: `/hunt-zones/${zone.slug || zone.id}` }],
  } : null);

  useEffect(() => {
    if (!identifier) return undefined;
    const controller = new AbortController();
    let current = true;
    setLoading(true);
    setError(false);
    void huntZonesApi.getByIdentifier(identifier, controller.signal).then((result) => {
      if (!current) return;
      setZone(result);
      setMapContext(tibiaMapApi.peekHuntZoneContext(result.slug || result.id) || tibiaMapApi.peekHuntZoneContext(result.id));
      if (result.slug && result.slug !== identifier) navigate(`/hunt-zones/${result.slug}`, { replace: true, state: location.state });
    }).catch(() => { if (current && !controller.signal.aborted) setError(true); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [identifier, location.state, navigate]);

  if (loading) return <Page><div className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /></div></Page>;
  if (!zone || error) return <Page><div className="rounded-2xl border border-danger/25 bg-danger-subtle p-6 text-danger"><h1 className="text-xl font-bold">{t('huntZoneDetail.unavailable')}</h1><p className="mt-2">{t('huntZoneDetail.notFound')}</p></div></Page>;

  const back = (location.state as { from?: string } | null)?.from || '/cyclopedia?tab=zones';
  const levelRange = zone.min_level != null && zone.min_level > 0 ? (zone.max_level ? `${zone.min_level}–${zone.max_level}` : `${zone.min_level}+`) : null;
  const accessMinimumLevel = zone.access?.minimum_level ?? null;
  const accessMaximumLevel = zone.access?.maximum_level ?? null;
  const accessLevelRange = accessMinimumLevel ? (accessMaximumLevel ? `${accessMinimumLevel}–${accessMaximumLevel}` : `${accessMinimumLevel}+`) : null;
  const accessPremiumRequired = zone.access?.premium_required ?? (zone.requires_premium ? true : null);
  const accessStatus = zone.access?.status ?? (zone.requires_premium || zone.requires_quest ? 'restricted' : 'unknown');
  const accessQuests = zone.access?.quests?.length ? zone.access.quests : (zone.requires_quest && zone.quest_name ? [{ id: zone.quest_id, name: zone.quest_name, slug: zone.quest_slug }] : []);
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
  const spatial = zone.spatial;
  const worldMap = spatial?.world_map;
  const hasMap = spatial?.geometry_status === 'mapped' && spatial.x != null && spatial.y != null && Boolean(worldMap);

  return <Page>
    <KnowledgeBackLink to={back}>{t('huntZoneDetail.back')}</KnowledgeBackLink>
    <KnowledgeHero
      eyebrow={t('huntZoneDetail.eyebrow')}
      title={zone.name}
      description={zone.description || undefined}
      media={hasMap ? <LocalizedMapPreview spatial={spatial} label={t('huntZoneDetail.mapAlt', { name: zone.name })} className="aspect-[4/3] rounded-2xl border border-line" /> : <div className="grid aspect-[4/3] place-items-center rounded-2xl border border-line bg-surface-base"><KnowledgeCategoryIcon category="zones" label={t('nav.zones')} className="size-28" mediaClassName="size-24" /></div>}
      badges={<>{zone.city ? <KnowledgeBadge tone="primary">{zone.city}</KnowledgeBadge> : null}{zone.region && zone.region !== zone.city ? <KnowledgeBadge>{zone.region}</KnowledgeBadge> : null}{zone.difficulty ? <KnowledgeBadge>{zone.difficulty}</KnowledgeBadge> : null}{accessPremiumRequired === true ? <KnowledgeBadge tone="warning">{t('huntZoneDetail.premium')}</KnowledgeBadge> : null}</>}
    />

    {quickFacts.length ? <div className="mt-6"><KnowledgeFacts>{quickFacts}</KnowledgeFacts></div> : null}

    <KnowledgeSection className="mt-6" title={t('huntZoneDetail.map')} icon={<MapPinned size={20} />}>
      {hasMap && spatial && worldMap ? <div className="overflow-hidden rounded-2xl"><Suspense fallback={<div className="grid min-h-72 place-items-center text-content-muted">{t('map.loading')}</div>}><TibiaMapViewer imageUrl={worldMap.image_url} pathfindingUrl={worldMap.pathfinding_url} label={zone.name} floor={spatial.z} floorLabel={spatial.z != null ? t('map.floor', { floor: formatDisplayFloor(spatial.z) }) : undefined} mapBounds={worldMap.bounds} center={{ x: spatial.x as number, y: spatial.y as number }} markers={(mapContext?.markers || []).map((marker) => ({ x: marker.x, y: marker.y, label: marker.name, imageUrl: marker.image_url }))} regions={spatial.bounds ? [{ minX: spatial.bounds.min_x, minY: spatial.bounds.min_y, maxX: spatial.bounds.max_x, maxY: spatial.bounds.max_y, label: zone.name }] : []} paths={(mapContext?.routes || []).map((route) => ({ id: route.id, label: route.name, points: route.points }))} coordinateMode="world" resetLabel={t('map.reset')} zoomInLabel={t('map.zoomIn')} zoomOutLabel={t('map.zoomOut')} emptyMessage={t('huntZoneDetail.mapEmpty')} /></Suspense><div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-content-muted"><span>{t('huntZoneDetail.coordinates', { x: spatial.x, y: spatial.y, z: spatial.z != null ? formatDisplayFloor(spatial.z) : t('common.unknown') })}</span><Link to={`/map?q=${encodeURIComponent(zone.name)}&entityType=hunt_zone&slug=${encodeURIComponent(zone.slug || String(zone.id))}&floor=${spatial.z}`} className="app-button-secondary app-button-sm">{t('huntZoneDetail.viewMap')}</Link></div></div> : <KnowledgeEmpty>{t('map.locationNotMapped')}</KnowledgeEmpty>}
    </KnowledgeSection>

    <div className="mt-8 space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(18rem,1fr)]">
        <div className="space-y-6">
          {ratingFacts.length ? <KnowledgeSection title={t('huntZoneDetail.ratings')} icon={<Gauge size={20} />}><KnowledgeFacts>{ratingFacts}</KnowledgeFacts></KnowledgeSection> : null}
          <KnowledgeSection title={t('huntZoneDetail.creatures')} icon={<Users size={20} />}>{zone.creature_spawns?.length ? <div className="grid gap-3 sm:grid-cols-2">{zone.creature_spawns.map((spawn) => spawn.creature ? <Link key={spawn.id} to={`/creatures/${spawn.creature.slug || spawn.creature.id}`} className="group flex min-h-20 items-center gap-3 rounded-xl border border-line bg-surface-base/60 p-3 hover:border-primary"><img src={`/api/v1/creatures/${spawn.creature.id}/image?placeholder=false`} alt="" className="size-14 shrink-0 object-contain [image-rendering:pixelated]" /><div><h3 className="font-semibold text-content-primary group-hover:text-primary">{spawn.creature.name}</h3>{spawn.quantity ? <p className="text-xs text-content-secondary">{t('huntZoneDetail.quantity')}: {spawn.quantity}</p> : null}{spawn.notes ? <p className="mt-1 text-xs text-content-muted">{spawn.notes}</p> : null}</div></Link> : null)}</div> : <KnowledgeEmpty>{t('huntZoneDetail.noCreatures')}</KnowledgeEmpty>}</KnowledgeSection>
          {zone.tips ? <KnowledgeSection title={t('huntZoneDetail.tips')} icon={<Sparkles size={20} />}><p className="whitespace-pre-line leading-7 text-content-secondary">{zone.tips}</p></KnowledgeSection> : null}
        </div>
        <div className="space-y-6">
          <KnowledgeSection title={t('huntZoneDetail.access')} icon={<Crown size={20} />}>
            {accessStatus === 'unknown' ? (
              <KnowledgeEmpty>{t('huntZoneDetail.accessUnknown')}</KnowledgeEmpty>
            ) : (
              <div className="space-y-4 text-sm text-content-secondary">
                <div className="flex flex-wrap gap-2">
                  {accessLevelRange ? <KnowledgeBadge tone="warning">{t('huntZoneDetail.minimumLevel', { level: accessLevelRange })}</KnowledgeBadge> : null}
                  {accessPremiumRequired === true ? <KnowledgeBadge tone="warning">{t('huntZoneDetail.premiumRequired')}</KnowledgeBadge> : null}
                  {accessPremiumRequired === false ? <KnowledgeBadge>{t('huntZoneDetail.premiumNotRequired')}</KnowledgeBadge> : null}
                </div>
                {accessQuests.length ? <div><p className="mb-2 font-semibold text-content-primary">{t('huntZoneDetail.accessQuests')}</p><div className="flex flex-wrap gap-2">{accessQuests.map((quest) => quest.slug || quest.id ? <Link key={quest.name} className="rounded-full border border-primary/35 bg-primary/10 px-3 py-1.5 font-semibold text-primary hover:bg-primary/15" to={`/quests/${quest.slug || quest.id}`}>{quest.name}</Link> : <span key={quest.name} className="rounded-full border border-line px-3 py-1.5 text-content-primary">{quest.name}</span>)}</div></div> : zone.access?.quest_required ? <p>{t('huntZoneDetail.questUnresolved')}</p> : null}
                {zone.access?.notes ? <p className="leading-6">{zone.access.notes}</p> : null}
              </div>
            )}
          </KnowledgeSection>
        </div>
      </div>
    </div>
    <div className="mt-6 flex justify-end"><SuggestCorrectionLink entityType="Hunt zone" entityName={zone.name} /></div>
  </Page>;
}
