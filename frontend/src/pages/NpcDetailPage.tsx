import { ArrowLeft, ArrowUpRight, Loader2, MapPin, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { namedKnowledgeApi } from '../services/api';
import type { NpcKnowledgeDetail } from '../types';
import MapMetadataPanel from '../components/MapMetadataPanel';
import { Page } from '../components/ui';

export default function NpcDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { identifier } = useParams<{ identifier: string }>();
  const [npc, setNpc] = useState<NpcKnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    if (!identifier) return () => controller.abort();
    void namedKnowledgeApi.getNpc(identifier, controller.signal)
      .then(setNpc)
      .catch(() => setNpc(null))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [identifier]);

  if (loading) return <Page variant="focused"><div role="status" className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /><span className="sr-only">{t('namedKnowledge.loading')}</span></div></Page>;
  if (!npc) return <Page variant="focused"><div className="mx-auto max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-6"><h1 className="text-lg font-semibold text-danger">{t('namedKnowledge.npcUnavailable')}</h1><p className="mt-2 text-sm text-danger/80">{t('namedKnowledge.notFound')}</p></div></Page>;

  const place = npc.relationships.find(relationship => relationship.relationship_type === 'located_at');
  return <Page variant="focused"><div>
    <button onClick={() => navigate(-1)} className="mb-6 flex min-h-11 items-center gap-2 text-content-secondary hover:text-content-primary"><ArrowLeft size={18} />{t('namedKnowledge.back')}</button>
    <article className="rounded-2xl border border-line bg-surface-base/70 p-4 sm:p-6">
      <header className="flex items-start gap-3"><UserRound className="mt-1 shrink-0 text-primary" /><div><p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{t('namedKnowledge.types.npc')}</p><h1 className="text-2xl font-bold text-content-primary sm:text-3xl">{npc.name}</h1>{npc.title && <p className="mt-1 text-primary">{npc.title}</p>}</div></header>
      <p className="mt-5 text-content-secondary">{npc.description || t('namedKnowledge.noDescription')}</p>
      <dl className="mt-6 grid gap-3 sm:grid-cols-2">
        {npc.occupation && <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.occupation')}</dt><dd className="mt-1 text-content-primary">{npc.occupation}</dd></div>}
        {npc.sex && <div className="rounded-lg bg-surface-base/60 p-3"><dt className="text-xs text-content-muted">{t('namedKnowledge.sex')}</dt><dd className="mt-1 text-content-primary">{npc.sex}</dd></div>}
      </dl>
      {(place || npc.location_name) && <section className="mt-6 rounded-xl border border-line p-4"><h2 className="mb-2 flex items-center gap-2 font-semibold text-primary"><MapPin size={16} />{t('namedKnowledge.location')}</h2>{place?.resolution_state === 'resolved' && place.target_slug
        ? <Link to={`/locations/${place.target_slug}`} className="flex min-h-11 items-center justify-between rounded-lg bg-surface-base/60 px-3 py-2 text-content-primary hover:text-primary"><span>{place.target_name}</span><ArrowUpRight size={15} /></Link>
        : <div className="min-h-11 rounded-lg bg-surface-base/60 px-3 py-2 text-content-secondary">{npc.location_name || place?.target_name}</div>}</section>}
      <MapMetadataPanel entityId={npc.knowledge_entity_id} />
      <footer className="mt-6 flex flex-wrap gap-3 text-xs text-content-muted">{npc.last_synced_at && <span>{t('namedKnowledge.updated', { date: new Date(npc.last_synced_at).toLocaleString() })}</span>}{npc.source_url && <a href={npc.source_url} target="_blank" rel="noreferrer" className="text-primary hover:text-primary">{t('namedKnowledge.source')}</a>}</footer>
    </article>
  </div></Page>;
}
