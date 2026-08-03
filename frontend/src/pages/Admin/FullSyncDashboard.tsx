import { Play, RefreshCw, RotateCcw, Square } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, FormField, Input, Select } from '../../components/ui';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import { FullSyncOptions, fullSyncApi, SyncJob } from '../../services/fullSync';
import SyncPhaseCard from './SyncPhaseCard';

const DEFAULTS: FullSyncOptions = { maintenance_enabled: true, continue_on_error: true, include_images: true, include_knowledge: true, include_guild_rosters: true, force_refresh: false, batch_size: 100, max_retries: 3, external_timeout_seconds: 30, operation_label: '', confirmation: 'SYNC EVERYTHING' };

function tone(status: string): 'neutral' | 'primary' | 'success' | 'warning' | 'danger' {
  if (status === 'completed' || status === 'success') return 'success';
  if (status === 'failed' || status === 'error' || status === 'cancelled') return 'danger';
  if (status === 'completed_with_errors' || status === 'retrying') return 'warning';
  return status === 'running' ? 'primary' : 'neutral';
}

export default function FullSyncDashboard() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [options, setOptions] = useState(DEFAULTS);
  const [busy, setBusy] = useState(false);
  const selected = useMemo(() => jobs.find(job => job.job_id === selectedId) || jobs.find(job => job.job_type === 'full') || null, [jobs, selectedId]);

  const load = async () => { const rows = await fullSyncApi.jobs(); setJobs(rows); if (!selectedId && rows.length) setSelectedId(rows.find(row => row.job_type === 'full')?.job_id || rows[0].job_id); };
  useEffect(() => { void load(); const interval = window.setInterval(() => void load(), 8_000); return () => window.clearInterval(interval); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    if (options.operation_label.trim().length < 5) return;
    if (!(await confirmation.confirm(t('fullSync.confirm', { phases: [t('fullSync.phases.creatures'), t('fullSync.phases.bosses'), t('fullSync.phases.items'), t('fullSync.phases.quests'), t('fullSync.phases.hunt-zones'), ...(options.include_images ? [t('fullSync.phases.images')] : []), ...(options.include_knowledge ? [t('fullSync.phases.knowledge')] : []), ...(options.include_guild_rosters ? [t('fullSync.phases.guild-rosters')] : [])].join(', ') }), { title: t('fullSync.startTitle'), confirmLabel: t('fullSync.start'), danger: true }))) return;
    setBusy(true);
    try { const result = await fullSyncApi.start({ ...options, operation_label: options.operation_label.trim() }); setSelectedId(result.job_id); await load(); toast.success(t('fullSync.queued', { id: result.job_id })); }
    catch { toast.error(t('fullSync.errors.start')); } finally { setBusy(false); }
  };
  const cancel = async () => { if (!selected || !(await confirmation.confirm(t('fullSync.cancelConfirm'), { danger: true }))) return; await fullSyncApi.cancel(selected.job_id); await load(); };
  const resume = async () => { if (!selected || !(await confirmation.confirm(t('fullSync.resumeConfirm')))) return; await fullSyncApi.resume(selected.job_id); await load(); };
  const resumePhase = async (phase: string) => { if (!selected) return; await fullSyncApi.resumePhase(selected.job_id, phase); await load(); };
  const skipPhase = async (phase: string) => { if (!selected) return; const reason = await confirmation.prompt(t('fullSync.skipConfirm', { phase }), { minimumLength: 5, danger: true }); if (!reason) return; await fullSyncApi.skipPhase(selected.job_id, phase, reason); await load(); };

  return <div className="space-y-6">
    <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">{t('fullSync.startTitle')}</h2><p className="text-sm text-content-secondary">{t('fullSync.startHelp')}</p></div><Link to="/admin/maintenance" className="app-button-secondary">{t('fullSync.maintenanceControls')}</Link></div>
      <div className="mt-5 grid gap-4 md:grid-cols-3"><FormField label={t('fullSync.label')} required><Input value={options.operation_label} onChange={event => setOptions(current => ({ ...current, operation_label: event.target.value }))} /></FormField><FormField label={t('fullSync.batch')}><Input type="number" min={10} max={500} value={options.batch_size} onChange={event => setOptions(current => ({ ...current, batch_size: Number(event.target.value) }))} /></FormField><FormField label={t('fullSync.retries')}><Select value={options.max_retries} onChange={event => setOptions(current => ({ ...current, max_retries: Number(event.target.value) }))}>{[0, 1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value}</option>)}</Select></FormField><FormField label={t('fullSync.timeout')}><Input type="number" min={5} max={120} value={options.external_timeout_seconds} onChange={event => setOptions(current => ({ ...current, external_timeout_seconds: Number(event.target.value) }))} /></FormField></div>
      <fieldset className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><legend className="sr-only">{t('fullSync.options')}</legend>{(['maintenance_enabled', 'continue_on_error', 'include_images', 'include_knowledge', 'include_guild_rosters', 'force_refresh'] as const).map(key => <label key={key} className="flex items-center gap-2 rounded-xl border border-line p-3 text-sm"><input type="checkbox" checked={options[key]} onChange={event => setOptions(current => ({ ...current, [key]: event.target.checked }))} />{t(`fullSync.optionsList.${key}`)}</label>)}</fieldset>
      <AppButton className="mt-5" onClick={() => void start()} disabled={options.operation_label.trim().length < 5} loading={busy}><Play className="size-4" />{t('fullSync.start')}</AppButton>
    </Card>

    <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]"><Card className="p-4"><div className="flex items-center justify-between"><h2 className="font-semibold">{t('fullSync.operations')}</h2><button aria-label={t('fullSync.refresh')} onClick={() => void load()}><RefreshCw className="size-4" /></button></div><div className="mt-3 space-y-2">{jobs.filter(job => job.job_type === 'full').map(job => <button key={job.job_id} onClick={() => setSelectedId(job.job_id)} className={`w-full rounded-xl border p-3 text-left ${job.job_id === selected?.job_id ? 'border-primary bg-primary-subtle' : 'border-line bg-surface-base'}`}><span className="block truncate text-sm font-medium">{job.operation_label || job.job_id}</span><span className="mt-1 flex items-center justify-between text-xs text-content-muted"><span>{job.operation_status}</span><span>{job.progress_percent}%</span></span></button>)}</div></Card>
      <Card className="p-5">{!selected ? <p className="text-content-muted">{t('fullSync.none')}</p> : <><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{selected.operation_label || selected.job_id}</h2><p className="mt-1 text-xs text-content-muted">{selected.job_id} · {selected.worker_id || t('fullSync.unclaimed')}</p></div><div className="flex items-center gap-2"><Badge tone={tone(selected.operation_status)}>{selected.operation_status}</Badge>{selected.maintenance_active && <Badge tone="warning">{t('fullSync.maintenanceActive')}</Badge>}</div></div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-base"><div className="h-full bg-primary" style={{ width: `${selected.progress_percent}%` }} /></div><p className="mt-2 text-sm text-content-secondary">{selected.message}</p>
        <dl className="mt-3 grid gap-2 text-xs text-content-muted sm:grid-cols-4"><div><dt>{t('fullSync.started')}</dt><dd>{selected.started_at ? new Date(selected.started_at).toLocaleString() : '—'}</dd></div><div><dt>{t('fullSync.updated')}</dt><dd>{selected.updated_at ? new Date(selected.updated_at).toLocaleString() : '—'}</dd></div><div><dt>{t('fullSync.finished')}</dt><dd>{selected.finished_at ? new Date(selected.finished_at).toLocaleString() : '—'}</dd></div><div><dt>{t('fullSync.autoRelease')}</dt><dd>{selected.maintenance_requested ? t('fullSync.enabled') : t('fullSync.disabled')}</dd></div></dl>
        <div className="mt-4 flex flex-wrap gap-2">{['failed', 'cancelled', 'completed_with_errors'].includes(selected.operation_status) && <AppButton size="sm" onClick={() => void resume()}><RotateCcw className="size-4" />{t('fullSync.resume')}</AppButton>}{['pending', 'running', 'retrying'].includes(selected.operation_status) && <AppButton size="sm" variant="danger" onClick={() => void cancel()}><Square className="size-4" />{t('fullSync.cancel')}</AppButton>}</div>
        <div className="mt-5 space-y-3">{selected.phases.map(phase => <SyncPhaseCard key={phase.id} jobId={selected.job_id} phase={phase} retryAllowed={selected.operation_status === 'completed_with_errors'} onRetry={() => void resumePhase(phase.phase_key)} onSkip={() => void skipPhase(phase.phase_key)} onRefresh={() => void load()} />)}</div>
        {selected.summary && <details className="mt-4"><summary className="cursor-pointer text-sm font-medium">{t('fullSync.summary')}</summary><pre className="mt-2 overflow-auto rounded-xl bg-surface-base p-3 text-xs">{JSON.stringify(selected.summary, null, 2)}</pre></details>}</>}</Card></div>
  </div>;
}
