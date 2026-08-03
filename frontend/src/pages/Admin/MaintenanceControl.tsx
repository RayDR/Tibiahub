import { RefreshCw, ShieldCheck, Wrench } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, FormField, Input, PageHeader, Textarea } from '../../components/ui';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import { maintenanceModeApi, MaintenanceStatus } from '../../services/maintenanceMode';

export default function MaintenanceControl() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);
  const [reason, setReason] = useState('');
  const [message, setMessage] = useState(t('maintenanceMode.defaultPublic'));
  const [plannedEnd, setPlannedEnd] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => { setStatus(await maintenanceModeApi.adminStatus()); };
  useEffect(() => { void load().catch(() => toast.error(t('maintenanceMode.errors.load'))); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const enable = async () => {
    if (reason.trim().length < 5 || message.trim().length < 5) return;
    if (!(await confirmation.confirm(t('maintenanceMode.enableConfirm'), { danger: true }))) return;
    setBusy(true);
    try { setStatus(await maintenanceModeApi.enableManual({ reason: reason.trim(), public_message: message.trim(), planned_end_at: plannedEnd ? new Date(plannedEnd).toISOString() : null, confirmation: 'ENABLE MAINTENANCE' })); toast.success(t('maintenanceMode.enabled')); }
    catch { toast.error(t('maintenanceMode.errors.action')); } finally { setBusy(false); }
  };
  const disable = async () => {
    const auditReason = await confirmation.prompt(t('maintenanceMode.disableConfirm'), { danger: true, minimumLength: 5, inputLabel: t('maintenanceMode.reason') });
    if (!auditReason) return;
    setBusy(true);
    try { setStatus(await maintenanceModeApi.disableManual(auditReason)); toast.success(t('maintenanceMode.disabled')); }
    catch { toast.error(t('maintenanceMode.errors.action')); } finally { setBusy(false); }
  };
  const release = async (id: number) => {
    const auditReason = await confirmation.prompt(t('maintenanceMode.releaseConfirm'), { danger: true, minimumLength: 5, inputLabel: t('maintenanceMode.reason') });
    if (!auditReason) return;
    try { await maintenanceModeApi.release(id, auditReason); await load(); toast.success(t('maintenanceMode.released')); }
    catch { toast.error(t('maintenanceMode.errors.action')); }
  };

  const manualActive = status?.holds?.some(hold => hold.hold_type === 'manual');
  return <div className="space-y-5">
    <PageHeader size="md" title={t('maintenanceMode.admin.title')} subtitle={t('maintenanceMode.admin.subtitle')} iconElement={<Wrench className="size-6" />} primaryAction={<AppButton variant="secondary" onClick={() => void load()}><RefreshCw className="size-4" />{t('maintenanceMode.refresh')}</AppButton>} />
    <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">{t('maintenanceMode.effective')}</h2><p className="text-sm text-content-secondary">{status?.message || t('maintenanceMode.onlineHelp')}</p></div><Badge tone={status?.active ? 'warning' : 'success'}>{status?.active ? t('maintenanceMode.active') : t('maintenanceMode.online')}</Badge></div></Card>
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="space-y-4 p-5"><h2 className="font-semibold">{t('maintenanceMode.manualTitle')}</h2>
        <FormField label={t('maintenanceMode.reason')} required><Textarea value={reason} onChange={event => setReason(event.target.value)} minLength={5} /></FormField>
        <FormField label={t('maintenanceMode.publicMessage')} required><Textarea value={message} onChange={event => setMessage(event.target.value)} minLength={5} /></FormField>
        <FormField label={t('maintenanceMode.plannedEnd')}><Input type="datetime-local" value={plannedEnd} onChange={event => setPlannedEnd(event.target.value)} /></FormField>
        <div className="flex flex-wrap gap-2"><AppButton onClick={() => void enable()} disabled={reason.trim().length < 5 || message.trim().length < 5} loading={busy}>{t('maintenanceMode.enable')}</AppButton><AppButton variant="danger" onClick={() => void disable()} disabled={!manualActive || busy}>{t('maintenanceMode.disable')}</AppButton></div>
      </Card>
      <Card className="p-5"><h2 className="font-semibold">{t('maintenanceMode.holds')}</h2><div className="mt-4 space-y-3">{status?.holds?.length ? status.holds.map(hold => <div key={hold.id} className="rounded-xl border border-line p-3"><div className="flex items-center justify-between gap-2"><Badge tone={hold.hold_type === 'sync' ? 'primary' : 'warning'}>{hold.hold_type}</Badge><span className="text-xs text-content-muted">#{hold.id}</span></div><p className="mt-2 text-sm">{hold.reason}</p><p className="mt-1 text-xs text-content-muted">{new Date(hold.enabled_at).toLocaleString()}{hold.owner_job_id ? ` · ${hold.owner_job_id}` : ''}</p><AppButton className="mt-3" size="sm" variant="secondary" onClick={() => void release(hold.id)}>{t('maintenanceMode.release')}</AppButton></div>) : <p className="text-sm text-content-muted">{t('maintenanceMode.noHolds')}</p>}</div></Card>
    </div>
    <Card className="flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-5" />{t('maintenanceMode.dataTitle')}</h2><p className="text-sm text-content-secondary">{t('maintenanceMode.dataHelp')}</p></div><Link className="app-button-secondary" to="/admin/maintenance/data">{t('maintenanceMode.openData')}</Link></Card>
  </div>;
}
