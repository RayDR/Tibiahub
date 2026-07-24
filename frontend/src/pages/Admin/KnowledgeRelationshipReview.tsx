import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, Link2, RefreshCw, ShieldCheck, XCircle } from 'lucide-react';
import { useToast } from '../../context/ToastContext';
import {
  knowledgeOperationsApi,
  type KnowledgeRelationshipProvenance,
  type KnowledgeRelationshipReview,
} from '../../services/knowledge';

type ReviewState = 'resolved' | 'unresolved' | 'ambiguous';

export default function KnowledgeRelationshipReviewPanel() {
  const { t } = useTranslation();
  const toast = useToast();
  const [state, setState] = useState<ReviewState>('unresolved');
  const [items, setItems] = useState<KnowledgeRelationshipReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<KnowledgeRelationshipProvenance | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setItems((await knowledgeOperationsApi.relationshipReview(state)).items);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [state]);
  useEffect(() => { void load(); }, [load]);

  const reason = () => window.prompt(t('knowledgeGraph.review.reasonPrompt'))?.trim() || '';
  const resolve = async (item: KnowledgeRelationshipReview, targetId: string) => {
    const value = reason();
    if (!value || !window.confirm(t('knowledgeGraph.review.confirmResolve', { name: item.unresolved_name }))) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.resolveRelationship(item.id, targetId, value);
      toast.success(t('knowledgeGraph.review.resolved'));
      await load();
    } catch {
      toast.error(t('knowledgeGraph.review.actionError'));
    } finally {
      setBusy(null);
    }
  };
  const reject = async (item: KnowledgeRelationshipReview) => {
    const value = reason();
    if (!value || !window.confirm(t('knowledgeGraph.review.confirmReject', { name: item.unresolved_name }))) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.rejectRelationship(item.id, value);
      toast.success(t('knowledgeGraph.review.rejected'));
      await load();
    } catch {
      toast.error(t('knowledgeGraph.review.actionError'));
    } finally {
      setBusy(null);
    }
  };
  const verify = async (item: KnowledgeRelationshipReview) => {
    const value = reason();
    if (!value || !window.confirm(t('knowledgeGraph.review.confirmVerify', { name: item.target_name }))) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.verifyRelationship(item.id, value);
      toast.success(t('knowledgeGraph.review.verified'));
      await load();
    } catch {
      toast.error(t('knowledgeGraph.review.actionError'));
    } finally {
      setBusy(null);
    }
  };

  return <section className="space-y-3 rounded-xl border border-slate-700 bg-slate-900/30 p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="flex items-center gap-2 font-medium text-slate-100"><Link2 className="h-4 w-4" />{t('knowledgeGraph.review.title')}</h3><p className="text-xs text-slate-400">{t('knowledgeGraph.review.subtitle')}</p></div>
      <button onClick={() => void load()} className="flex min-h-11 items-center gap-2 rounded-lg border border-slate-700 px-3 text-sm"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />{t('knowledgeGraph.review.refresh')}</button>
    </div>
    <div className="flex flex-wrap gap-2" role="tablist">
      {(['unresolved', 'ambiguous', 'resolved'] as const).map(value => <button key={value} role="tab" aria-selected={state === value} onClick={() => setState(value)} className={`min-h-11 rounded-lg px-3 text-sm ${state === value ? 'bg-amber-600 text-white' : 'border border-slate-700 text-slate-300'}`}>{t(`knowledgeGraph.states.${value}`)}</button>)}
    </div>
    {error ? <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-200"><AlertCircle className="mr-2 inline h-4 w-4" />{t('knowledgeGraph.review.loadError')}</div>
      : !loading && items.length === 0 ? <p className="rounded-lg border border-slate-700 p-4 text-sm text-slate-400">{t('knowledgeGraph.review.empty')}</p>
        : <div className="grid gap-3 md:grid-cols-2">{items.map(item => <article key={item.id} className="rounded-xl border border-slate-700 bg-slate-950/60 p-4">
          <div className="flex justify-between gap-2"><div><strong className="text-slate-100">{item.source_name}</strong><p className="text-xs text-slate-400">{t(`knowledgeGraph.relationships.${item.relationship_type}`)}</p></div><span className="text-xs text-amber-300">{t(`knowledgeGraph.states.${item.resolution_state}`)}</span></div>
          <p className="mt-3 text-sm text-slate-200">{item.target_name || item.unresolved_name}</p>
          <p className="mt-1 text-xs text-slate-500">{t('knowledgeGraph.review.source', { provider: item.provider_id || t('knowledgeGraph.review.local'), confidence: item.confidence })}</p>
          {item.candidates.length > 0 && <div className="mt-3 space-y-2"><p className="text-xs text-slate-400">{t('knowledgeGraph.review.candidates')}</p>{item.candidates.map(candidate => <button disabled={busy === item.id} key={candidate.id} onClick={() => void resolve(item, candidate.id)} className="flex min-h-11 w-full items-center justify-between rounded-lg border border-emerald-500/30 px-3 text-left text-sm text-emerald-200"><span>{candidate.name}</span><ShieldCheck className="h-4 w-4" /></button>)}</div>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={() => void knowledgeOperationsApi.relationshipProvenance(item.id).then(setProvenance).catch(() => toast.error(t('knowledgeGraph.review.provenanceError')))} className="min-h-11 rounded-lg border border-slate-700 px-3 text-xs">{t('knowledgeGraph.review.provenance')}</button>
            {item.resolution_state === 'resolved' ? <button disabled={busy === item.id} onClick={() => void verify(item)} className="flex min-h-11 items-center gap-1 rounded-lg border border-emerald-500/30 px-3 text-xs text-emerald-300"><ShieldCheck className="h-4 w-4" />{t('knowledgeGraph.review.verify')}</button>
              : <button disabled={busy === item.id} onClick={() => void reject(item)} className="flex min-h-11 items-center gap-1 rounded-lg border border-red-500/30 px-3 text-xs text-red-300"><XCircle className="h-4 w-4" />{t('knowledgeGraph.review.reject')}</button>}
          </div>
        </article>)}</div>}
    {provenance && <div className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300"><div className="flex justify-between"><strong>{t('knowledgeGraph.review.provenance')}</strong><button onClick={() => setProvenance(null)}>{t('knowledgeGraph.review.close')}</button></div><p className="mt-2">{t('knowledgeGraph.review.provenanceSummary', { provider: provenance.provider_id || t('knowledgeGraph.review.local'), count: Object.keys(provenance.safe_context).length })}</p></div>}
  </section>;
}
