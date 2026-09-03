import { ArrowLeft, ArrowUpRight, BookOpenCheck, CircleHelp, Coins, Loader2, MapPin, Navigation, PackageOpen, Route, UserRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import MapMetadataPanel from '../components/MapMetadataPanel';
import { Badge, EmptyState, Page, PageHeader } from '../components/ui';
import { namedKnowledgeApi } from '../services/api';
import type { NamedKnowledgeRelationship, NpcKnowledgeDetail, NpcNamedReference } from '../types';
import { createCyclopediaRouteState, resolveCyclopediaReturnTarget } from '../utils/cyclopediaNavigation';
import { useSeoMetadata } from '../utils/seo';

function ReferenceList({ values, empty, ambiguous }: { values: NpcNamedReference[]; empty: string; ambiguous: string }) {
  if (!values.length) return empty ? <p className="text-sm text-content-muted">{empty}</p> : null;
  return <ul className="grid gap-2 sm:grid-cols-2">
    {values.map((value, index) => <li key={`${value.name}:${index}`}>
      {value.resolution_state === 'resolved' && value.navigation_url
        ? <Link to={value.navigation_url} className="flex min-h-11 items-center justify-between gap-2 rounded-lg border border-line bg-surface-base/50 px-3 py-2 text-sm text-content-primary hover:border-primary/40 hover:text-primary"><span className="min-w-0 truncate">{value.name}{value.price != null ? ` · ${value.price} gp` : ''}</span><ArrowUpRight className="size-4 shrink-0" /></Link>
        : <div className="flex min-h-11 items-center justify-between gap-2 rounded-lg border border-line bg-surface-base/40 px-3 py-2 text-sm text-content-secondary"><span>{value.name}{value.price != null ? ` · ${value.price} gp` : ''}</span>{value.resolution_state === 'ambiguous' ? <Badge tone="warning">{ambiguous}</Badge> : null}</div>}
    </li>)}
  </ul>;
}

function QuestRelationships({ values }: { values: NamedKnowledgeRelationship[] }) {
  const { t } = useTranslation();
  if (!values.length) return null;
  return <ul className="grid gap-2 sm:grid-cols-2">
    {values.map(value => <li key={value.canonical_id}>
      {value.resolution_state === 'resolved' && value.target_slug
        ? <Link to={`/quests/${value.target_slug}`} className="flex min-h-11 items-center justify-between gap-2 rounded-lg border border-line bg-surface-base/50 px-3 py-2 text-sm hover:border-primary/40"><span><span className="block font-medium text-content-primary">{value.target_name}</span><span className="text-xs text-content-muted">{t(`npcDetail.questSemantics.${value.relationship_type}`, { defaultValue: t('npcDetail.questSemantics.related') })}</span></span><ArrowUpRight className="size-4 text-primary" /></Link>
        : <div className="min-h-11 rounded-lg border border-line bg-surface-base/40 px-3 py-2 text-sm text-content-secondary">{value.target_name}</div>}
    </li>)}
  </ul>;
}

export default function NpcDetailPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { identifier } = useParams<{ identifier: string }>();
  const [npc, setNpc] = useState<NpcKnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useSeoMetadata(npc ? {
    title: t('npcDetail.seoTitle', { name: npc.name }),
    description: npc.description || t('npcDetail.seoDescription', { name: npc.name }),
    canonicalPath: `/npcs/${npc.canonical_id}`,
    type: 'article',
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: t('npcDirectory.title'), path: '/npcs' }, { name: npc.name, path: `/npcs/${npc.canonical_id}` }],
  } : null);

  useEffect(() => {
    const controller = new AbortController();
    if (!identifier) return () => controller.abort();
    setLoading(true);
    void namedKnowledgeApi.getNpc(identifier, controller.signal)
      .then(result => {
        setNpc(result);
        if (result.canonical_id !== identifier) navigate(`/npcs/${result.canonical_id}`, { replace: true, state: location.state });
      })
      .catch(() => setNpc(null))
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [identifier, location.state, navigate]);

  const questRelationships = useMemo(() => (npc?.relationships || []).filter(value => value.target_type === 'quest'), [npc?.relationships]);
  const locations = useMemo(() => (npc?.relationships || []).filter(value => ['located_at', 'hosts_npc'].includes(value.relationship_type)), [npc?.relationships]);

  if (loading) return <Page variant="focused"><div role="status" className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /><span className="sr-only">{t('namedKnowledge.loading')}</span></div></Page>;
  if (!npc) return <Page variant="focused"><EmptyState icon={<UserRound />} title={t('namedKnowledge.npcUnavailable')} description={t('namedKnowledge.notFound')} action={<Link to="/npcs" className="app-button-secondary">{t('npcDetail.back')}</Link>} /></Page>;

  const backTarget = resolveCyclopediaReturnTarget((location.state as { from?: string } | null)?.from, '/npcs');
  const cyclopediaState = createCyclopediaRouteState(backTarget);
  const tradeKnown = npc.field_coverage.buys !== 'unknown' || npc.field_coverage.sells !== 'unknown';
  const destinationsKnown = npc.field_coverage.destinations !== 'unknown';
  const questsKnown = npc.field_coverage.related_quests !== 'unknown' || questRelationships.length > 0;

  return <Page variant="focused">
    <button onClick={() => navigate(backTarget)} className="mb-4 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft className="size-4" />{t('npcDetail.back')}</button>
    <article>
      <PageHeader eyebrow={t('npcDetail.eyebrow')} title={npc.name} subtitle={npc.title || npc.occupation || undefined} iconElement={<UserRound className="size-7" />} breadcrumbs={[{ label: t('npcDirectory.title'), to: '/npcs' }, { label: npc.name }]} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          <section className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6" aria-labelledby="npc-overview">
            <h2 id="npc-overview" className="text-lg font-semibold text-content-primary">{t('npcDetail.overview')}</h2>
            <p className="mt-3 text-content-secondary">{npc.description || t('namedKnowledge.noDescription')}</p>
            <dl className="mt-5 grid gap-3 sm:grid-cols-2">
              {npc.occupation ? <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.occupation')}</dt><dd className="mt-1 text-content-primary">{npc.occupation}</dd></div> : null}
              {npc.sex ? <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.sex')}</dt><dd className="mt-1 text-content-primary">{npc.sex}</dd></div> : null}
            </dl>
            {npc.aliases.length ? <p className="mt-4 text-xs text-content-muted">{t('npcDetail.aliases')}: {npc.aliases.join(', ')}</p> : null}
          </section>

          <section className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6" aria-labelledby="npc-location">
            <h2 id="npc-location" className="flex items-center gap-2 text-lg font-semibold text-content-primary"><MapPin className="size-5 text-primary" />{t('namedKnowledge.location')}</h2>
            <div className="mt-3 grid gap-2">
              {locations.length ? locations.map(place => place.resolution_state === 'resolved' && place.target_slug
                ? <Link key={place.canonical_id} to={`/locations/${place.target_slug}`} state={cyclopediaState} className="flex min-h-11 items-center justify-between rounded-lg border border-line bg-surface-base/50 px-3 py-2 text-content-primary hover:border-primary/40"><span>{place.target_name}</span><ArrowUpRight className="size-4" /></Link>
                : <div key={place.canonical_id} className="min-h-11 rounded-lg border border-line bg-surface-base/40 px-3 py-2 text-content-secondary">{place.target_name}</div>)
                : npc.location_name ? <div className="min-h-11 rounded-lg border border-line bg-surface-base/40 px-3 py-2 text-content-secondary">{npc.location_name}<span className="ml-2 text-xs text-content-muted">{t('npcDetail.locationText')}</span></div>
                  : <p className="text-sm text-content-muted">{t('npcDetail.unknownLocation')}</p>}
            </div>
            {locations.length > 1 ? <p className="mt-3 text-xs text-content-muted">{t('npcDetail.multipleLocations')}</p> : null}
          </section>

          <section className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6" aria-labelledby="npc-trade">
            <h2 id="npc-trade" className="flex items-center gap-2 text-lg font-semibold text-content-primary"><Coins className="size-5 text-primary" />{t('npcDetail.trade')}</h2>
            {!tradeKnown ? <div className="mt-3 flex gap-2 text-sm text-content-muted"><CircleHelp className="size-4 shrink-0" />{t('npcDetail.tradeUnknown')}</div> : <div className="mt-4 grid gap-5 lg:grid-cols-2">
              <div><h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-content-primary"><PackageOpen className="size-4" />{t('npcDetail.buys')}</h3><p className="mb-3 text-xs text-content-muted">{t('npcDetail.buysHelp')}</p><ReferenceList values={npc.buys} empty={t(npc.field_coverage.buys === 'unknown' ? 'npcDetail.buysUnknown' : 'npcDetail.buysNone')} ambiguous={t('npcDetail.ambiguous')} /></div>
              <div><h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-content-primary"><PackageOpen className="size-4" />{t('npcDetail.sells')}</h3><p className="mb-3 text-xs text-content-muted">{t('npcDetail.sellsHelp')}</p><ReferenceList values={npc.sells} empty={t(npc.field_coverage.sells === 'unknown' ? 'npcDetail.sellsUnknown' : 'npcDetail.sellsNone')} ambiguous={t('npcDetail.ambiguous')} /></div>
            </div>}
          </section>

          <section className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6" aria-labelledby="npc-quests">
            <h2 id="npc-quests" className="flex items-center gap-2 text-lg font-semibold text-content-primary"><BookOpenCheck className="size-5 text-primary" />{t('npcDetail.quests')}</h2>
            {!questsKnown ? <p className="mt-3 text-sm text-content-muted">{t('npcDetail.questsUnknown')}</p> : <div className="mt-3 space-y-3"><QuestRelationships values={questRelationships} /><ReferenceList values={npc.related_quests.filter(raw => !questRelationships.some(graph => graph.target_canonical_id && graph.target_canonical_id === raw.canonical_id))} empty={questRelationships.length ? '' : t('npcDetail.questsNone')} ambiguous={t('npcDetail.ambiguous')} /></div>}
          </section>

          <section className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6" aria-labelledby="npc-travel">
            <h2 id="npc-travel" className="flex items-center gap-2 text-lg font-semibold text-content-primary"><Route className="size-5 text-primary" />{t('npcDetail.travel')}</h2>
            {!destinationsKnown ? <p className="mt-3 text-sm text-content-muted">{t('npcDetail.travelUnknown')}</p> : <div className="mt-3"><ReferenceList values={npc.destinations} empty={t('npcDetail.travelNone')} ambiguous={t('npcDetail.ambiguous')} /></div>}
          </section>

          <MapMetadataPanel entityId={npc.knowledge_entity_id} mapTarget={{ entityType: 'npc', name: npc.name, slug: npc.slug, canonicalEntityId: npc.knowledge_entity_id }} />
        </div>

        <aside className="space-y-4 lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-2xl border border-line bg-surface-base/70 p-4">
            <div className="grid aspect-square place-items-center rounded-xl bg-primary/10 text-primary">
              {npc.media.status === 'available' && npc.media.url ? <img src={npc.media.url} alt="" className="size-full object-contain [image-rendering:pixelated]" /> : <UserRound className="size-20" aria-hidden="true" />}
            </div>
            <p className="mt-3 text-xs text-content-muted">{npc.media.status === 'reference_only' ? t('npcDetail.mediaReferenceOnly') : npc.media.status === 'missing' ? t('npcDetail.mediaMissing') : t('npcDetail.mediaAvailable')}</p>
          </div>
          <div className="rounded-2xl border border-line bg-surface-base/70 p-4 text-xs text-content-muted">
            <h2 className="font-semibold text-content-primary">{t('npcDetail.provenance')}</h2>
            <p className="mt-2">{t('npcDetail.provider', { provider: npc.source_provider })}</p>
            {npc.last_synced_at ? <p className="mt-1">{t('namedKnowledge.updated', { date: new Date(npc.last_synced_at).toLocaleString() })}</p> : null}
            {npc.source_url ? <a href={npc.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-11 items-center gap-1 text-primary hover:text-primary-hover">{t('namedKnowledge.source')}<ArrowUpRight className="size-3.5" /></a> : null}
          </div>
          {npc.spatial.geometry_status === 'mapped' ? <Link to={`/map?entity=${encodeURIComponent(npc.canonical_id)}&entityType=npc`} className="app-button-secondary w-full justify-center"><Navigation className="size-4" />{t('npcDetail.openMap')}</Link> : null}
        </aside>
      </div>
    </article>
  </Page>;
}
