import { ArrowLeft, ArrowUpRight, Loader2, MapPin } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { namedKnowledgeApi } from '../services/api';
import type { LocationKnowledgeDetail, NamedKnowledgeRelationship } from '../types';
import MapMetadataPanel from '../components/MapMetadataPanel';

function relationshipPath(relationship: NamedKnowledgeRelationship): string | null {
  if (relationship.resolution_state !== 'resolved' || !relationship.target_slug) return null;
  if (relationship.target_type === 'npc') return `/npcs/${relationship.target_slug}`;
  if (['location', 'area', 'town'].includes(relationship.target_type)) return `/locations/${relationship.target_slug}`;
  if (relationship.target_type === 'quest') return `/quests/${relationship.target_slug}`;
  return null;
}

export default function LocationDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { identifier } = useParams<{ identifier: string }>();
  const [place, setPlace] = useState<LocationKnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    if (!identifier) return () => controller.abort();
    void namedKnowledgeApi.getLocation(identifier, controller.signal)
      .then(setPlace)
      .catch(() => setPlace(null))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [identifier]);

  if (loading) return <div role="status" className="flex min-h-screen items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /><span className="sr-only">{t('namedKnowledge.loading')}</span></div>;
  if (!place) return <div className="mx-auto mt-28 max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-6"><h1 className="text-lg font-semibold text-danger">{t('namedKnowledge.locationUnavailable')}</h1><p className="mt-2 text-sm text-danger/80">{t('namedKnowledge.notFound')}</p></div>;

  return <main className="min-h-screen pb-20 pt-28"><div className="container mx-auto max-w-5xl px-4">
    <button onClick={() => navigate(-1)} className="mb-6 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft size={18} />{t('namedKnowledge.back')}</button>
    <article className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6">
      <header className="flex items-start gap-3"><MapPin className="mt-1 shrink-0 text-primary" /><div><p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{t(`namedKnowledge.types.${place.entity_type}`)}</p><h1 className="text-2xl font-bold text-content-primary sm:text-3xl">{place.name}</h1>{place.location_kind && <p className="mt-1 text-primary">{place.location_kind}</p>}</div></header>
      <p className="mt-5 text-content-secondary">{place.description || t('namedKnowledge.noDescription')}</p>
      <dl className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {place.region && <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.region')}</dt><dd className="mt-1 text-content-primary">{place.region}</dd></div>}
        {place.minimum_level != null && <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.minimumLevel')}</dt><dd className="mt-1 text-content-primary">{place.minimum_level}</dd></div>}
        {place.premium_required != null && <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.premium')}</dt><dd className="mt-1 text-content-primary">{t(place.premium_required ? 'namedKnowledge.yes' : 'namedKnowledge.no')}</dd></div>}
      </dl>
      {place.access_notes && <section className="mt-6 rounded-xl border border-line p-4"><h2 className="font-semibold text-primary">{t('namedKnowledge.access')}</h2><p className="mt-2 text-sm text-content-secondary">{place.access_notes}</p></section>}
      {place.relationships.length > 0 && <section className="mt-6 rounded-xl border border-line p-4"><h2 className="mb-3 font-semibold text-primary">{t('namedKnowledge.relationships')}</h2><ul className="space-y-2">{place.relationships.map((relationship, index) => { const path = relationshipPath(relationship); const content = <><span><span className="text-xs text-content-muted">{t(`knowledgeGraph.relationships.${relationship.relationship_type}`)}</span><span className="block text-content-primary">{relationship.target_name}</span></span>{path && <ArrowUpRight size={15} className="text-primary" />}</>; return <li key={`${relationship.relationship_type}-${relationship.target_name}-${index}`}>{path ? <Link to={path} className="flex min-h-11 items-center justify-between rounded-lg bg-surface-base/60 px-3 py-2 hover:ring-1 hover:ring-primary/40">{content}</Link> : <div className="flex min-h-11 items-center rounded-lg bg-surface-base/60 px-3 py-2">{content}</div>}</li>; })}</ul></section>}
      <MapMetadataPanel locationIdentifier={place.slug} />
      <footer className="mt-6 flex flex-wrap gap-3 text-xs text-content-muted">{place.last_synced_at && <span>{t('namedKnowledge.updated', { date: new Date(place.last_synced_at).toLocaleString() })}</span>}{place.source_url && <a href={place.source_url} target="_blank" rel="noreferrer" className="text-primary hover:text-primary">{t('namedKnowledge.source')}</a>}</footer>
    </article>
  </div></main>;
}
