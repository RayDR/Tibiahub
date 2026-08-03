import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge } from '../../components/ui';
import { SyncPhase } from '../../services/fullSync';
import { fullSyncApi } from '../../services/fullSync';
import { useToast } from '../../context/ToastContext';
import SyncErrorDialog from './SyncErrorDialog';

function tone(status: string): 'neutral' | 'primary' | 'success' | 'warning' | 'danger' {
  if (status === 'completed') return 'success';
  if (status === 'failed' || status === 'cancelled') return 'danger';
  if (status === 'retrying') return 'warning';
  return status === 'running' ? 'primary' : 'neutral';
}

export default function SyncPhaseCard({ jobId, phase, retryAllowed, onRetry, onSkip, onRefresh }: {
  jobId: string;
  phase: SyncPhase;
  retryAllowed: boolean;
  onRetry: () => void;
  onSkip: () => void;
  onRefresh: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const [errorsOpen, setErrorsOpen] = useState(false);
  const [canaryBusy, setCanaryBusy] = useState(false);
  const failurePercent = phase.processed_count > 0 ? (phase.failed_count / phase.processed_count) * 100 : 0;
  const highFailure = phase.phase_key === 'images' && failurePercent > 25;
  const blindRetryBlocked = phase.phase_key === 'images' && failurePercent > 80 && !phase.canary_validated;
  const incomplete = ['failed', 'cancelled', 'skipped'].includes(phase.status);

  return <div className={`rounded-xl border p-4 ${highFailure ? 'border-danger bg-danger-subtle' : 'border-line'}`}>
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2">{phase.status === 'completed' ? <CheckCircle2 className="size-4 text-success" /> : phase.status === 'running' ? <Loader2 className="size-4 animate-spin text-primary" /> : phase.status === 'failed' ? <AlertTriangle className="size-4 text-danger" /> : null}<span className="font-medium">{t(`fullSync.phases.${phase.phase_key}`)}</span><Badge>{phase.provider || t('fullSync.local')}</Badge></div><Badge tone={tone(phase.status)}>{phase.status}</Badge></div>
    <dl className="mt-3 grid gap-2 text-xs text-content-secondary sm:grid-cols-4"><div><dt>{t('fullSync.processed')}</dt><dd>{phase.processed_count}</dd></div><div><dt>{t('fullSync.failed')}</dt><dd>{phase.failed_count}{phase.phase_key === 'images' && ` (${failurePercent.toFixed(1)}%)`}</dd></div><div><dt>{t('fullSync.offset')}</dt><dd>{phase.current_offset}</dd></div><div><dt>{t('fullSync.attempt')}</dt><dd>{phase.attempt_count}/{phase.max_attempts}</dd></div></dl>
    {highFailure && <p className="mt-3 rounded-lg border border-danger p-2 text-xs text-danger">{t(blindRetryBlocked ? 'fullSync.errorViewer.canaryRequired' : phase.canary_validated ? 'imageCanary.passed' : 'fullSync.errorViewer.highFailure')}</p>}
    {phase.current_entity && <p className="mt-2 text-xs text-content-muted">{t('fullSync.entity')}: {phase.current_entity}</p>}
    {phase.next_retry_at && <p className="mt-2 text-xs text-warning">{t('fullSync.nextRetry')}: {new Date(phase.next_retry_at).toLocaleString()}</p>}
    {phase.last_error && <div className="mt-3 rounded-lg bg-surface-base p-3 text-xs"><p className="font-medium text-danger">{phase.last_error.safe_message}</p><p className="mt-1 text-content-muted">{phase.last_error.entity_name || '—'} · {phase.last_error.category || '—'}{phase.last_error.http_status ? ` · HTTP ${phase.last_error.http_status}` : ''} · {t('fullSync.errorViewer.affected', { count: phase.last_error.affected_count })}</p></div>}
    {Object.keys(phase.checkpoint).length > 0 && <details className="mt-2"><summary className="cursor-pointer text-xs font-medium">{t('fullSync.checkpoint')}</summary><pre className="mt-1 overflow-auto rounded-lg bg-surface-base p-2 text-xs">{JSON.stringify(phase.checkpoint, null, 2)}</pre></details>}
    <div className="mt-3 flex flex-wrap gap-2">{(phase.failed_count > 0 || phase.last_error) && <AppButton size="sm" variant="secondary" onClick={() => setErrorsOpen(true)}>{t('fullSync.errorViewer.view')}</AppButton>}{phase.phase_key === 'images' && highFailure && <AppButton size="sm" variant="secondary" loading={canaryBusy} onClick={async () => { setCanaryBusy(true); try { const result = await fullSyncApi.runImageCanary(30); result.passed ? toast.success(t('imageCanary.success', { succeeded: result.succeeded, total: result.total })) : toast.error(t('imageCanary.failure', { failed: result.failed, total: result.total })); onRefresh(); } catch { toast.error(t('imageCanary.error')); } finally { setCanaryBusy(false); } }}>{t('imageCanary.run')}</AppButton>}</div>
    {incomplete && <div className="mt-3 flex gap-2"><AppButton size="sm" variant="secondary" disabled={!retryAllowed || blindRetryBlocked} onClick={onRetry}>{t('fullSync.retryPhase')}</AppButton>{!phase.required && phase.status !== 'skipped' && <AppButton size="sm" variant="ghost" onClick={onSkip}>{t('fullSync.skip')}</AppButton>}</div>}
    <SyncErrorDialog jobId={jobId} phase={phase.phase_key} open={errorsOpen} onClose={() => setErrorsOpen(false)} />
  </div>;
}
