import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, Ban, Clock3, Loader2, Play, RefreshCw, RotateCcw, Server, Workflow } from 'lucide-react';
import { useToast } from '../../context/ToastContext';
import {
  knowledgeOperationsApi,
  type KnowledgeJob,
  type KnowledgeJobDetail,
  type KnowledgeProvider,
  type KnowledgeWorkerHeartbeat,
} from '../../services/knowledge';

const jobStates = ['', 'pending', 'claimed', 'running', 'retrying', 'failed', 'succeeded', 'partially_succeeded', 'cancelled'];
const providerEntityJobTypes = new Set([
  'creature_catalog', 'creature_detail', 'creature_renormalize',
  'item_catalog', 'item_detail', 'item_renormalize',
  'quest_catalog', 'quest_detail', 'quest_renormalize',
]);

function JobTypeLabel({ value }: { value: string }) {
  const { t } = useTranslation();
  const known = ['reference_import', ...providerEntityJobTypes];
  return <>{known.includes(value) ? t(`knowledgeOps.jobTypes.${value}`) : value}</>;
}

function SectionError({ message, retry }: { message: string; retry: () => void }) {
  const { t } = useTranslation();
  return <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><AlertCircle className="mr-2 inline h-4 w-4" />{message}<button onClick={retry} className="ml-3 underline">{t('knowledgeOps.actions.retryLoad')}</button></div>;
}

function StatusBadge({ value }: { value: string }) {
  const { t } = useTranslation();
  const color = value === 'healthy' || value === 'succeeded' || value === 'idle' ? 'bg-emerald-500/15 text-emerald-300' : value === 'failed' || value === 'unavailable' ? 'bg-red-500/15 text-red-300' : value === 'disabled' || value === 'cancelled' ? 'bg-slate-700 text-slate-300' : 'bg-amber-500/15 text-amber-300';
  return <span className={`rounded-full px-2 py-1 text-xs ${color}`}>{t(`knowledgeOps.status.${value}`)}</span>;
}

export default function KnowledgeOperations() {
  const { t } = useTranslation();
  const toast = useToast();
  const [providers, setProviders] = useState<KnowledgeProvider[]>([]);
  const [workers, setWorkers] = useState<KnowledgeWorkerHeartbeat[]>([]);
  const [jobs, setJobs] = useState<KnowledgeJob[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [providerError, setProviderError] = useState(false);
  const [workerError, setWorkerError] = useState(false);
  const [jobError, setJobError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyJob, setBusyJob] = useState<string | null>(null);
  const [details, setDetails] = useState<KnowledgeJobDetail | null>(null);
  const [providerFilter, setProviderFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [enqueueProvider, setEnqueueProvider] = useState('');
  const [enqueueEntity, setEnqueueEntity] = useState('');
  const [enqueueJobType, setEnqueueJobType] = useState('');
  const [canonicalName, setCanonicalName] = useState('');
  const [languageNeutralId, setLanguageNeutralId] = useState('');
  const [externalId, setExternalId] = useState('');
  const [pageTitle, setPageTitle] = useState('');
  const [batchLimit, setBatchLimit] = useState(10);

  const loadProviders = useCallback(async () => {
    setProviderError(false);
    try { setProviders(await knowledgeOperationsApi.providers()); } catch { setProviderError(true); }
  }, []);
  const loadWorkers = useCallback(async () => {
    setWorkerError(false);
    try { setWorkers(await knowledgeOperationsApi.workers()); } catch { setWorkerError(true); }
  }, []);
  const loadJobs = useCallback(async () => {
    setJobError(false);
    try {
      const page = await knowledgeOperationsApi.jobs({ provider_id: providerFilter || undefined, entity_type: entityFilter || undefined, state: stateFilter || undefined, limit: 50 });
      setJobs(page.items); setTotalJobs(page.total);
    } catch { setJobError(true); }
  }, [entityFilter, providerFilter, stateFilter]);
  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.allSettled([loadProviders(), loadWorkers(), loadJobs()]);
    setLoading(false);
  }, [loadJobs, loadProviders, loadWorkers]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const selectedProvider = providers.find(provider => provider.provider_id === enqueueProvider);
  const availableProviders = providers.filter(provider => provider.enabled && provider.supported_job_types.length > 0);
  const entityOptions = useMemo(() => Array.from(new Set(providers.flatMap(provider => provider.supports_entities))).sort(), [providers]);
  const availableJobTypes = (selectedProvider?.supported_job_types || []).filter(jobType => (
    jobType === 'reference_import' ? enqueueEntity === 'creature' : jobType.startsWith(`${enqueueEntity}_`)
  ));
  const isCatalog = enqueueJobType.endsWith('_catalog');
  const isDetail = enqueueJobType.endsWith('_detail');
  const isRenormalize = enqueueJobType.endsWith('_renormalize');
  const isProviderEntityJob = providerEntityJobTypes.has(enqueueJobType);
  const canEnqueue = Boolean(selectedProvider && enqueueEntity && enqueueJobType) && (
    isCatalog
      ? batchLimit >= 1 && batchLimit <= 50
      : isDetail
        ? Boolean(externalId.trim() || pageTitle.trim())
        : isRenormalize
          ? Boolean(externalId.trim())
          : Boolean(canonicalName.trim() && languageNeutralId.trim())
  );

  const enqueue = async () => {
    if (!canEnqueue || !selectedProvider) return;
    if (isCatalog && !window.confirm(t('knowledgeOps.confirm.catalog', { entity: t(`knowledgeOps.entities.${enqueueEntity}`) }))) return;
    setBusyJob('enqueue');
    try {
      const scope = isCatalog ? { batch_limit: batchLimit } : {};
      const payload = isProviderEntityJob
        ? {
            ...(externalId.trim() ? { external_id: externalId.trim() } : {}),
            ...(isDetail && pageTitle.trim() ? { page_title: pageTitle.trim() } : {}),
          }
        : { canonical_name: canonicalName.trim(), language_neutral_id: languageNeutralId.trim(), provider_document_id: languageNeutralId.trim() };
      const result = await knowledgeOperationsApi.enqueue({
        provider_id: selectedProvider.provider_id,
        job_type: enqueueJobType,
        entity_type: enqueueEntity,
        scope,
        payload,
        confirm_catalog_sync: isCatalog,
        allow_completed_recreate: isProviderEntityJob,
      });
      toast.success(t(result.created ? 'knowledgeOps.messages.enqueued' : 'knowledgeOps.messages.alreadyActive'));
      setCanonicalName(''); setLanguageNeutralId(''); setExternalId(''); setPageTitle('');
      await loadJobs();
    } catch { toast.error(t('knowledgeOps.errors.enqueue')); }
    finally { setBusyJob(null); }
  };

  const transition = async (job: KnowledgeJob, action: 'retry' | 'cancel') => {
    if (!window.confirm(t(`knowledgeOps.confirm.${action}`))) return;
    setBusyJob(job.id);
    try {
      if (action === 'retry') await knowledgeOperationsApi.retry(job.id); else await knowledgeOperationsApi.cancel(job.id);
      toast.success(t(`knowledgeOps.messages.${action}`));
      await loadJobs();
      if (details?.id === job.id) setDetails(await knowledgeOperationsApi.job(job.id));
    } catch { toast.error(t(`knowledgeOps.errors.${action}`)); }
    finally { setBusyJob(null); }
  };

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-lg font-semibold text-slate-100">{t('knowledgeOps.title')}</h2><p className="text-sm text-slate-400">{t('knowledgeOps.subtitle')}</p></div>
      <button onClick={() => void loadAll()} disabled={loading} className="flex min-h-11 items-center gap-2 rounded-lg border border-slate-700 px-3 text-sm text-slate-300"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />{t('knowledgeOps.actions.refresh')}</button>
    </div>

    <section className="space-y-3"><h3 className="flex items-center gap-2 font-medium text-slate-200"><Server className="h-4 w-4" />{t('knowledgeOps.providers.title')}</h3>
      {providerError ? <SectionError message={t('knowledgeOps.errors.providers')} retry={() => void loadProviders()} /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{providers.map(provider => <article key={provider.provider_id} className="rounded-xl border border-slate-700 bg-slate-900/50 p-4"><div className="flex items-center justify-between gap-2"><strong className="text-slate-100">{provider.provider_name}</strong><StatusBadge value={provider.health} /></div><p className="mt-2 text-xs text-slate-400">{t('knowledgeOps.providers.failures', { count: provider.consecutive_failures })}</p><p className="mt-1 text-xs text-slate-500">{t('knowledgeOps.providers.entities', { value: provider.supports_entities.join(', ') || t('knowledgeOps.common.none') })}</p><p className="mt-1 text-xs text-slate-500">{t('knowledgeOps.providers.jobTypes', { value: provider.supported_job_types.length ? provider.supported_job_types.map(value => t(`knowledgeOps.jobTypes.${value}`)).join(', ') : t('knowledgeOps.common.none') })}</p><p className="mt-1 text-xs text-slate-500">{provider.last_success_at ? t('knowledgeOps.providers.freshness', { value: new Date(provider.last_success_at).toLocaleString() }) : t('knowledgeOps.providers.neverSynced')}</p></article>)}</div>}
    </section>

    <section className="space-y-3"><h3 className="flex items-center gap-2 font-medium text-slate-200"><Workflow className="h-4 w-4" />{t('knowledgeOps.workers.title')}</h3>
      {workerError ? <SectionError message={t('knowledgeOps.errors.workers')} retry={() => void loadWorkers()} /> : workers.length === 0 ? <p className="rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-400">{t('knowledgeOps.workers.empty')}</p> : <div className="grid gap-3 sm:grid-cols-2">{workers.map(worker => <article key={worker.worker_id} className="rounded-xl border border-slate-700 bg-slate-900/50 p-4"><div className="flex justify-between"><strong className="text-slate-100">{worker.worker_id}</strong><StatusBadge value={worker.state} /></div><p className="mt-2 text-xs text-slate-400">{t('knowledgeOps.workers.lastSeen', { value: new Date(worker.last_seen_at).toLocaleString() })}</p></article>)}</div>}
    </section>

    <section className="space-y-3 rounded-xl border border-slate-700 bg-slate-900/30 p-4"><h3 className="font-medium text-slate-200">{t('knowledgeOps.enqueue.title')}</h3><p className="text-xs text-slate-400">{t('knowledgeOps.enqueue.help')}</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <select aria-label={t('knowledgeOps.fields.provider')} value={enqueueProvider} onChange={event => { setEnqueueProvider(event.target.value); setEnqueueJobType(''); setEnqueueEntity(''); }} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm"><option value="">{t('knowledgeOps.fields.provider')}</option>{availableProviders.map(provider => <option key={provider.provider_id} value={provider.provider_id}>{provider.provider_name}</option>)}</select>
        <select aria-label={t('knowledgeOps.fields.entityType')} value={enqueueEntity} onChange={event => { setEnqueueEntity(event.target.value); setEnqueueJobType(''); }} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm"><option value="">{t('knowledgeOps.fields.entityType')}</option>{(selectedProvider?.supports_entities || []).map(entity => <option key={entity} value={entity}>{t(`knowledgeOps.entities.${entity}`)}</option>)}</select>
        <select aria-label={t('knowledgeOps.fields.jobType')} value={enqueueJobType} onChange={event => setEnqueueJobType(event.target.value)} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm"><option value="">{t('knowledgeOps.fields.jobType')}</option>{availableJobTypes.map(jobType => <option key={jobType} value={jobType}>{<JobTypeLabel value={jobType} />}</option>)}</select>
        {isCatalog ? <input type="number" min={1} max={50} value={batchLimit} onChange={event => setBatchLimit(Number(event.target.value))} placeholder={t('knowledgeOps.fields.batchLimit')} aria-label={t('knowledgeOps.fields.batchLimit')} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm" /> : isProviderEntityJob ? <><input value={externalId} onChange={event => setExternalId(event.target.value)} placeholder={t('knowledgeOps.fields.externalId')} aria-label={t('knowledgeOps.fields.externalId')} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm" />{isDetail && <input value={pageTitle} onChange={event => setPageTitle(event.target.value)} placeholder={t(`knowledgeOps.fields.${enqueueEntity}Name`)} aria-label={t(`knowledgeOps.fields.${enqueueEntity}Name`)} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm" />}</> : <><input value={canonicalName} onChange={event => setCanonicalName(event.target.value)} placeholder={t('knowledgeOps.fields.canonicalName')} aria-label={t('knowledgeOps.fields.canonicalName')} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm" /><input value={languageNeutralId} onChange={event => setLanguageNeutralId(event.target.value)} placeholder={t('knowledgeOps.fields.languageNeutralId')} aria-label={t('knowledgeOps.fields.languageNeutralId')} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm" /></>}
      </div>{isCatalog && <p className="text-xs text-amber-300">{t('knowledgeOps.enqueue.catalogWarning')}</p>}<button onClick={() => void enqueue()} disabled={busyJob === 'enqueue' || !canEnqueue} className="flex min-h-11 items-center gap-2 rounded-lg bg-amber-600 px-4 text-sm font-medium text-white disabled:opacity-50">{busyJob === 'enqueue' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{t('knowledgeOps.actions.enqueue')}</button>
      {availableProviders.length === 0 && <p className="text-xs text-amber-300">{t('knowledgeOps.enqueue.disabled')}</p>}
    </section>

    <section className="space-y-3"><div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="font-medium text-slate-200">{t('knowledgeOps.jobs.title')}</h3><p className="text-xs text-slate-500">{t('knowledgeOps.jobs.count', { count: totalJobs })}</p></div><div className="flex flex-wrap gap-2"><select aria-label={t('knowledgeOps.filters.provider')} value={providerFilter} onChange={event => setProviderFilter(event.target.value)} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-2 text-sm"><option value="">{t('knowledgeOps.filters.allProviders')}</option>{providers.map(provider => <option key={provider.provider_id} value={provider.provider_id}>{provider.provider_name}</option>)}</select><select aria-label={t('knowledgeOps.filters.entity')} value={entityFilter} onChange={event => setEntityFilter(event.target.value)} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-2 text-sm"><option value="">{t('knowledgeOps.filters.allEntities')}</option>{entityOptions.map(entity => <option key={entity} value={entity}>{entity}</option>)}</select><select aria-label={t('knowledgeOps.filters.state')} value={stateFilter} onChange={event => setStateFilter(event.target.value)} className="min-h-11 rounded-lg border border-slate-700 bg-slate-950 px-2 text-sm">{jobStates.map(state => <option key={state || 'all'} value={state}>{state ? t(`knowledgeOps.status.${state}`) : t('knowledgeOps.filters.allStates')}</option>)}</select></div></div>
      {jobError ? <SectionError message={t('knowledgeOps.errors.jobs')} retry={() => void loadJobs()} /> : jobs.length === 0 ? <p className="rounded-lg border border-slate-700 bg-slate-900/50 p-5 text-center text-sm text-slate-400">{t('knowledgeOps.jobs.empty')}</p> : <div className="grid gap-3 md:grid-cols-2">{jobs.map(job => <article key={job.id} className="rounded-xl border border-slate-700 bg-slate-900/50 p-4"><div className="flex items-start justify-between gap-2"><div><strong className="text-slate-100"><JobTypeLabel value={job.job_type} /></strong><p className="text-xs text-slate-500">{job.provider_id} · {job.entity_type || t('knowledgeOps.common.providerWide')}</p>{job.parent_job_id && <p className="text-xs text-slate-500">{t('knowledgeOps.jobs.childOf', { value: job.parent_job_id.slice(0, 8) })}</p>}</div><StatusBadge value={job.state} /></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400"><span>{t('knowledgeOps.jobs.attempts', { current: job.attempt_count, max: job.max_attempts })}</span><span><Clock3 className="mr-1 inline h-3 w-3" />{new Date(job.scheduled_at).toLocaleString()}</span></div>{job.safe_last_error && <p className="mt-3 rounded bg-red-500/10 p-2 text-xs text-red-200">{job.safe_last_error}</p>}<div className="mt-3 flex flex-wrap gap-2"><button onClick={() => void knowledgeOperationsApi.job(job.id).then(setDetails).catch(() => toast.error(t('knowledgeOps.errors.details')))} className="min-h-11 rounded-lg border border-slate-700 px-3 text-xs">{t('knowledgeOps.actions.details')}</button>{job.can_retry && <button onClick={() => void transition(job, 'retry')} disabled={busyJob === job.id} className="flex min-h-11 items-center gap-1 rounded-lg border border-amber-500/40 px-3 text-xs text-amber-300"><RotateCcw className="h-3 w-3" />{t('knowledgeOps.actions.retry')}</button>}{job.can_cancel && <button onClick={() => void transition(job, 'cancel')} disabled={busyJob === job.id} className="flex min-h-11 items-center gap-1 rounded-lg border border-red-500/40 px-3 text-xs text-red-300"><Ban className="h-3 w-3" />{t('knowledgeOps.actions.cancel')}</button>}</div></article>)}</div>}
    </section>

    {details && <section className="rounded-xl border border-slate-700 bg-slate-950/60 p-4"><div className="flex justify-between"><h3 className="font-medium text-slate-200">{t('knowledgeOps.attempts.title')}</h3><button onClick={() => setDetails(null)} className="text-sm text-slate-400">{t('knowledgeOps.actions.close')}</button></div>{details.attempts.length === 0 ? <p className="mt-3 text-sm text-slate-500">{t('knowledgeOps.attempts.empty')}</p> : <div className="mt-3 space-y-2">{details.attempts.slice().reverse().map(attempt => <div key={attempt.id} className="rounded-lg border border-slate-800 p-3 text-xs"><div className="flex justify-between"><span>{t('knowledgeOps.attempts.number', { value: attempt.attempt_number })}</span><StatusBadge value={attempt.outcome} /></div>{attempt.safe_error && <p className="mt-2 text-red-200">{attempt.safe_error}</p>}<p className="mt-2 text-slate-500">{t('knowledgeOps.attempts.worker', { value: attempt.worker_id })}</p>{Object.keys(attempt.metrics).length > 0 && <><p className="mt-2 text-slate-400">{t('knowledgeOps.attempts.metrics', { created: attempt.metrics.entities_created || 0, updated: attempt.metrics.entities_updated || 0, unchanged: attempt.metrics.entities_unchanged || 0, children: attempt.metrics.child_jobs_enqueued || 0, warnings: (attempt.metrics.warnings || 0) + (attempt.metrics.invalid_members || 0) })}</p>{(attempt.metrics.missions_total || attempt.metrics.relations_resolved || attempt.metrics.relations_unresolved || attempt.metrics.relations_ambiguous) ? <p className="mt-1 text-slate-400">{t('knowledgeOps.attempts.questMetrics', { missions: attempt.metrics.missions_total || 0, resolved: attempt.metrics.relations_resolved || 0, unresolved: attempt.metrics.relations_unresolved || 0, ambiguous: attempt.metrics.relations_ambiguous || 0 })}</p> : null}</>}</div>)}</div>}</section>}
  </div>;
}
