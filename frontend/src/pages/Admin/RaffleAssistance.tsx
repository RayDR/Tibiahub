import { CalendarClock, Search, ShieldAlert } from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, FormField, Input, Select, Textarea } from '../../components/ui';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import { adminAssistanceApi, AssistedRaffle } from '../../services/adminAssistance';
import { appLocale } from '../../utils/locale';

function localInput(utcValue: string | null, timezone: string): string {
  if (!utcValue) return '';
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(utcValue)).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function formatInZone(value: string | null, timezone: string, locale: string): string {
  return value ? new Intl.DateTimeFormat(locale, { timeZone: timezone, dateStyle: 'medium', timeStyle: 'long' }).format(new Date(value)) : '—';
}

function localToUtc(value: string, timezone: string): string | null {
  if (!value) return null;
  const expected = Date.parse(`${value}:00Z`);
  if (Number.isNaN(expected)) return null;
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
  let candidate = expected;
  for (let index = 0; index < 2; index += 1) {
    const parts = Object.fromEntries(formatter.formatToParts(new Date(candidate)).map(part => [part.type, part.value]));
    const observed = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour), Number(parts.minute), Number(parts.second));
    candidate += expected - observed;
  }
  return new Date(candidate).toISOString();
}

export default function RaffleAssistance() {
  const { t, i18n } = useTranslation();
  const locale = appLocale(i18n.resolvedLanguage || i18n.language);
  const toast = useToast();
  const confirmation = useConfirmation();
  const [identifier, setIdentifier] = useState('');
  const [raffle, setRaffle] = useState<AssistedRaffle | null>(null);
  const [localSchedule, setLocalSchedule] = useState('');
  const [timezone, setTimezone] = useState('America/Chicago');
  const [reason, setReason] = useState('');
  const [snapshotDecision, setSnapshotDecision] = useState<'preserve' | 'invalidate'>('preserve');
  const [busy, setBusy] = useState(false);
  const newUtc = useMemo(() => localToUtc(localSchedule, timezone), [localSchedule, timezone]);
  const timezoneOptions = useMemo(() => Array.from(new Set([raffle?.timezone_name, 'America/Chicago', 'America/New_York', 'America/Denver', 'America/Los_Angeles', 'America/Sao_Paulo', 'Europe/London', 'Europe/Berlin', 'UTC'].filter((value): value is string => Boolean(value)))), [raffle?.timezone_name]);

  const lookup = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true);
    try {
      const row = await adminAssistanceApi.lookupRaffle(identifier);
      const selectedZone = row.timezone_name || 'America/Chicago';
      setRaffle(row); setTimezone(selectedZone); setLocalSchedule(localInput(row.scheduled_run_at_utc, selectedZone)); setSnapshotDecision('preserve');
    } catch { toast.error(t('raffleAssistance.errors.lookup')); }
    finally { setBusy(false); }
  };

  const submit = async () => {
    if (!raffle || !newUtc || reason.trim().length < 5) return;
    const accepted = await confirmation.confirm(t('raffleAssistance.confirm', {
      old: raffle.scheduled_run_at_utc ? formatInZone(raffle.scheduled_run_at_utc, raffle.timezone_name, locale) : t('maintenanceMode.common.unknown'),
      next: formatInZone(newUtc, timezone, locale), timezone,
    }), { title: t('raffleAssistance.preview'), confirmLabel: t('raffleAssistance.reschedule'), danger: true });
    if (!accepted) return;
    setBusy(true);
    try {
      const result = await adminAssistanceApi.rescheduleRaffle(raffle.public_code, {
        local_scheduled_at: localSchedule, timezone_name: timezone, expected_version: raffle.version,
        reason: reason.trim(), explicit_confirmation: true, snapshot_decision: snapshotDecision,
      });
      setRaffle(result.raffle); setLocalSchedule(localInput(result.raffle.scheduled_run_at_utc, result.raffle.timezone_name));
      toast.success(t('raffleAssistance.success', { id: result.audit_id }));
    } catch { toast.error(t('raffleAssistance.errors.reschedule')); }
    finally { setBusy(false); }
  };

  return <div className="workspace-page">
    <WorkspaceContentHeader title={t('raffleAssistance.title')} description={t('raffleAssistance.subtitle')} icon={<CalendarClock />} />
    <Card className="p-5"><form className="flex flex-col gap-3 sm:flex-row" onSubmit={lookup}><Input value={identifier} onChange={event => setIdentifier(event.target.value)} placeholder={t('raffleAssistance.searchPlaceholder')} required /><AppButton loading={busy}><Search className="size-4" />{t('raffleAssistance.search')}</AppButton></form></Card>
    {raffle && <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
      <Card className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">{raffle.title}</h2><p className="text-sm text-content-secondary">{raffle.guild_name} · {t(`raffle.operations.${raffle.purpose}`, raffle.purpose)}</p></div><Badge tone={raffle.safe_to_reschedule ? 'success' : 'danger'}>{raffle.safe_to_reschedule ? t('raffleAssistance.safe') : t('raffleAssistance.unsafe')}</Badge></div>
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">{t('raffleAssistance.id')}</dt><dd>{raffle.id}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.code')}</dt><dd>{raffle.public_code}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.participants')}</dt><dd>{raffle.participant_count}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.state')}</dt><dd>{t(`raffle.workspace.status.${raffle.status}`, raffle.status)} / {t(`raffle.workspace.execution.${raffle.execution_state}`, raffle.execution_state)}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.local')}</dt><dd>{formatInZone(raffle.scheduled_run_at_utc, raffle.timezone_name, locale)}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.utc')}</dt><dd>{raffle.scheduled_run_at_utc ? new Date(raffle.scheduled_run_at_utc).toISOString() : '—'}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.snapshotState')}</dt><dd>{raffle.eligibility_snapshot.exists ? (raffle.eligibility_snapshot.valid ? t('raffleAssistance.snapshotValid') : t('raffleAssistance.snapshotInvalid')) : t('raffleAssistance.snapshotNone')}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.schedulerState')}</dt><dd>{raffle.scheduler.job_id || '—'} · {t('raffleAssistance.attempts')} {raffle.scheduler.attempt_count}</dd></div></dl>
        <details className="mt-4 text-sm"><summary className="cursor-pointer font-medium">{t('raffleAssistance.schedulerDetails')}</summary><dl className="mt-2 grid gap-2 rounded-xl bg-surface-base p-3 sm:grid-cols-2"><div><dt className="text-content-muted">{t('raffleAssistance.claimed')}</dt><dd>{raffle.scheduler.claimed_at || '—'}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.lease')}</dt><dd>{raffle.scheduler.lease_expires_at || '—'}</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.retry')}</dt><dd>{raffle.scheduler.next_retry_at || '—'} ({raffle.scheduler.retry_count})</dd></div><div><dt className="text-content-muted">{t('raffleAssistance.lastError')}</dt><dd>{raffle.scheduler.last_error_code || '—'}</dd></div></dl></details>
        {!raffle.safe_to_reschedule && <p className="mt-4 flex gap-2 rounded-xl bg-danger-subtle p-3 text-sm text-danger"><ShieldAlert className="size-5 shrink-0" />{t('raffleAssistance.blocked', { reason: raffle.unsafe_reason })}</p>}
        {raffle.eligibility_snapshot.warning && <p className="mt-4 rounded-xl bg-warning-subtle p-3 text-sm text-warning">{raffle.eligibility_snapshot.warning}</p>}
      </Card>
      <Card className="space-y-4 p-5"><h2 className="font-semibold">{t('raffleAssistance.newSchedule')}</h2>
        <FormField label={t('raffleAssistance.localDateTime')} required><Input type="datetime-local" value={localSchedule} onChange={event => setLocalSchedule(event.target.value)} /></FormField>
        <FormField label={t('raffleAssistance.timezone')} required><Select value={timezone} onChange={event => setTimezone(event.target.value)}>{timezoneOptions.map(value => <option key={value} value={value}>{value}</option>)}</Select></FormField>
        {raffle.eligibility_snapshot.exists && <FormField label={t('raffleAssistance.snapshot')}><Select value={snapshotDecision} onChange={event => setSnapshotDecision(event.target.value as 'preserve' | 'invalidate')}><option value="preserve">{t('raffleAssistance.preserve')}</option><option value="invalidate">{t('raffleAssistance.invalidate')}</option></Select></FormField>}
        <FormField label={t('raffleAssistance.reason')} required><Textarea value={reason} onChange={event => setReason(event.target.value)} minLength={5} /></FormField>
        <div className="rounded-xl bg-surface-base p-3 text-xs"><p>{t('raffleAssistance.previewOld')}: {raffle.scheduled_run_at_utc || '—'}</p><p className="mt-1">{t('raffleAssistance.previewNew')}: {newUtc || '—'}</p></div>
        <AppButton className="w-full" onClick={() => void submit()} disabled={!raffle.safe_to_reschedule || !newUtc || reason.trim().length < 5} loading={busy}>{t('raffleAssistance.reschedule')}</AppButton>
      </Card>
    </div>}
  </div>;
}
