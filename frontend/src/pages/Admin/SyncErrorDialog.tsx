import { RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Dialog } from '../../components/ui';
import { fullSyncApi, SyncPhaseErrors } from '../../services/fullSync';
import { formatDateTime } from '../../utils/locale';

const PAGE_SIZE = 25;

export default function SyncErrorDialog({ jobId, phase, open, onClose }: {
  jobId: string;
  phase: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(0);
  const [data, setData] = useState<SyncPhaseErrors | null>(null);
  const [loading, setLoading] = useState(false);
  const load = async () => {
    setLoading(true);
    try { setData(await fullSyncApi.phaseErrors(jobId, phase, page * PAGE_SIZE, PAGE_SIZE)); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (open) void load(); }, [open, page, jobId, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  return <Dialog open={open} onClose={onClose} label={t('fullSync.errorViewer.title')} className="max-h-[90vh] max-w-4xl overflow-y-auto p-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="font-semibold">{t(`fullSync.phases.${phase}`)}</h2><p className="text-xs text-content-muted">{data ? t('fullSync.errorViewer.affected', { count: data.total_affected_entities }) : '—'}</p></div>
      <AppButton size="sm" variant="secondary" onClick={() => void load()} loading={loading}><RefreshCw className="size-4" />{t('fullSync.errorViewer.refresh')}</AppButton>
    </div>
    {data && <>
      {!data.detail_recorded && data.historical_message && <p className="mt-4 rounded-xl border border-warning bg-warning-subtle p-3 text-sm text-warning">{t('fullSync.errorViewer.historical')}</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {([['categories', data.top_error_categories], ['statuses', data.top_http_statuses], ['providers', data.top_provider_hosts]] as const).map(([label, values]) => <section key={label} className="rounded-xl border border-line p-3"><h3 className="text-xs font-semibold uppercase text-content-muted">{t(`fullSync.errorViewer.${label}`)}</h3><div className="mt-2 flex flex-wrap gap-1">{values.length ? values.map(entry => <Badge key={String(entry.value)}>{String(entry.value)} · {entry.count}</Badge>) : '—'}</div></section>)}
      </div>
      <div className="mt-4 space-y-3">{data.rows.map(row => <article key={`${row.external_id}-${row.error_category}-${row.http_status}`} className="rounded-xl border border-line p-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm font-medium">{row.entity_name || row.external_id || t('fullSync.errorViewer.unknownEntity')}</p><p className="text-xs text-content-muted">{formatDateTime(row.last_seen_at, i18n.resolvedLanguage || i18n.language)} · {row.provider || '—'}</p></div><Badge tone={row.retryable ? 'warning' : 'danger'}>{row.retryable ? t('fullSync.errorViewer.retryable') : t('fullSync.errorViewer.permanent')}</Badge></div>
        <p className="mt-2 text-sm text-content-secondary">{row.safe_message}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-content-muted"><span>{row.error_category}</span>{row.http_status && <span>HTTP {row.http_status}</span>}{row.occurrence_count > 1 && <span>×{row.occurrence_count}</span>}{row.url && <span className="max-w-full truncate">{row.url}</span>}</div>
      </article>)}</div>
      <div className="mt-4 flex items-center justify-between"><AppButton size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage(value => value - 1)}>{t('fullSync.errorViewer.previous')}</AppButton><span className="text-xs text-content-muted">{t('fullSync.errorViewer.page', { page: page + 1 })}</span><AppButton size="sm" variant="secondary" disabled={(page + 1) * PAGE_SIZE >= data.total_error_records} onClick={() => setPage(value => value + 1)}>{t('fullSync.errorViewer.next')}</AppButton></div>
    </>}
  </Dialog>;
}
