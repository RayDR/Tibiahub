import { FormEvent, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AutomaticRaffleDraw from '../../components/raffle/AutomaticRaffleDraw';
import { useAuth } from '../../context/AuthContext';
import { AutomaticRun, EligibilityPreview, Raffle, raffleApi } from '../../services/raffle';

function wallTimeToUtc(value: string, timeZone: string): string {
  if (!value) return '';
  const [date, time] = value.split('T');
  const [year, month, day] = date.split('-').map(Number);
  const [hour, minute] = time.split(':').map(Number);
  const target = Date.UTC(year, month - 1, day, hour, minute);
  let guess = target;
  for (let iteration = 0; iteration < 2; iteration += 1) {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(guess));
    const part = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((entry) => entry.type === type)?.value);
    const represented = Date.UTC(part('year'), part('month') - 1, part('day'), part('hour'), part('minute'));
    guess = target - (represented - guess);
  }
  return new Date(guess).toISOString();
}

export default function AutomaticRaffleOperations() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [raffles, setRaffles] = useState<Raffle[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [preview, setPreview] = useState<EligibilityPreview | null>(null);
  const [runs, setRuns] = useState<AutomaticRun[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [purpose, setPurpose] = useState<'test' | 'real'>('test');
  const [title, setTitle] = useState('');
  const [guild, setGuild] = useState(user?.guild_name || '');
  const [timezone, setTimezone] = useState('America/Chicago');
  const [schedule, setSchedule] = useState('');
  const [confirmedReal, setConfirmedReal] = useState(false);
  const [rerunPositions, setRerunPositions] = useState<Array<'second' | 'first'>>([]);
  const [rerunReason, setRerunReason] = useState('');
  const [testCharacter, setTestCharacter] = useState('');

  const selected = raffles.find((raffle) => raffle.id === selectedId) || null;
  const successfulRuns = runs.filter((run) => run.state === 'succeeded');
  const latestRun = successfulRuns[successfulRuns.length - 1];
  let scheduledUtc = '';
  try { scheduledUtc = wallTimeToUtc(schedule, timezone); } catch { scheduledUtc = ''; }
  const scheduledLocal = scheduledUtc ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'full', timeStyle: 'short', timeZone: timezone }).format(new Date(scheduledUtc)) : '—';

  const load = async (target?: number) => {
    const data = (await raffleApi.list()).filter((raffle) => raffle.run_mode === 'automatic' && raffle.purpose !== 'legacy');
    setRaffles(data);
    setSelectedId(target ?? selectedId ?? data[0]?.id ?? null);
  };
  useEffect(() => { void load().catch(() => setError(t('raffle.operations.errors.load'))); }, []);
  useEffect(() => {
    if (!selectedId) { setRuns([]); return; }
    void raffleApi.runs(selectedId).then(setRuns).catch(() => setError(t('raffle.operations.errors.load')));
  }, [selectedId, selected?.current_run_number]);

  const create = async (event: FormEvent) => {
    event.preventDefault(); setError('');
    if (purpose === 'real' && !confirmedReal) { setError(t('raffle.operations.errors.confirmReal')); return; }
    if (!scheduledUtc || (purpose === 'real' && new Date(scheduledUtc) <= new Date())) { setError(t('raffle.operations.errors.future')); return; }
    setBusy(true);
    try {
      const prizes = [
        { name: t('raffle.operations.secondPlace'), reward: '100 TC', order_index: 1, position: 'second' as const, amount: 100, currency: 'TC' },
        { name: t('raffle.operations.firstPlace'), reward: '250 TC', order_index: 2, position: 'first' as const, amount: 250, currency: 'TC' },
      ];
      const created = await raffleApi.create({ title, guild_name: guild, access_mode: 'guild_only', show_participants: false, prizes, purpose, run_mode: 'automatic', scheduled_run_at: scheduledUtc, timezone_name: timezone, eligibility_days: 5 });
      await load(created.id); setTitle(''); setSchedule(''); setConfirmedReal(false);
    } catch { setError(t('raffle.operations.errors.create')); } finally { setBusy(false); }
  };

  const refreshSelected = async () => { if (!selectedId) return; const fresh = await raffleApi.get(selectedId); setRaffles((rows) => rows.map((row) => row.id === fresh.id ? fresh : row)); setRuns(await raffleApi.runs(selectedId)); };
  const performRerun = async () => {
    if (!selected || rerunPositions.length === 0 || rerunReason.trim().length < 3) return;
    setBusy(true); try { await raffleApi.rerunAutomatic(selected.id, rerunPositions, rerunReason); await refreshSelected(); setRerunPositions([]); setRerunReason(''); } catch { setError(t('raffle.operations.errors.rerun')); } finally { setBusy(false); }
  };
  const canPublish = Boolean(user?.is_superuser || ['leader', 'guild leader'].includes((user?.guild_rank || '').toLowerCase()));
  const stale = preview && Date.now() - new Date(preview.cutoff_at).getTime() > 60 * 60 * 1000;

  return <div className="space-y-6">
    <header><h1 className="text-2xl font-bold text-slate-100">{t('raffle.operations.title')}</h1><p className="text-slate-400">{t('raffle.operations.subtitle')}</p></header>
    {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-red-950/30 p-3 text-red-200">{error}</div>}
    <form onSubmit={create} className="grid gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 md:grid-cols-2">
      <h2 className="md:col-span-2 text-lg font-semibold">{t('raffle.operations.prepare')}</h2>
      <label>{t('raffle.operations.purpose')}<select value={purpose} onChange={(e) => setPurpose(e.target.value as 'test' | 'real')} className="mt-1 w-full rounded-lg bg-slate-950 p-2"><option value="test">{t('raffle.operations.test')}</option><option value="real">{t('raffle.operations.real')}</option></select></label>
      <label>{t('raffle.operations.guild')}<input value={guild} onChange={(e) => setGuild(e.target.value)} required className="mt-1 w-full rounded-lg bg-slate-950 p-2" /></label>
      <label>{t('raffle.operations.name')}<input value={title} onChange={(e) => setTitle(e.target.value)} required className="mt-1 w-full rounded-lg bg-slate-950 p-2" /></label>
      <label>{t('raffle.operations.timezone')}<input value={timezone} onChange={(e) => setTimezone(e.target.value)} required className="mt-1 w-full rounded-lg bg-slate-950 p-2" /></label>
      <label>{t('raffle.operations.localSchedule')}<input type="datetime-local" value={schedule} onChange={(e) => setSchedule(e.target.value)} required className="mt-1 w-full rounded-lg bg-slate-950 p-2" /></label>
      <div className="rounded-lg border border-slate-800 p-3 text-sm"><p>{t('raffle.operations.localEquivalent', { value: scheduledLocal })}</p><p>{t('raffle.operations.utcEquivalent', { value: scheduledUtc || '—' })}</p></div>
      <div className="md:col-span-2 rounded-xl border border-amber-500/20 p-3 text-sm text-slate-300">{t('raffle.operations.rules')}</div>
      <div className="md:col-span-2 grid gap-2 sm:grid-cols-2"><div className="rounded-lg bg-slate-950 p-3">{t('raffle.operations.secondPlace')} — 100 TC</div><div className="rounded-lg bg-slate-950 p-3">{t('raffle.operations.firstPlace')} — 250 TC</div></div>
      {purpose === 'real' && <label className="md:col-span-2 flex gap-2"><input type="checkbox" checked={confirmedReal} onChange={(e) => setConfirmedReal(e.target.checked)} />{t('raffle.operations.confirmReal')}</label>}
      <button disabled={busy} className="md:col-span-2 rounded-lg bg-amber-500 p-2 font-bold text-slate-950">{t('raffle.operations.save')}</button>
      <p className="md:col-span-2 text-xs text-slate-500">{t('raffle.operations.fridayExample')}</p>
    </form>

    <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <div className="space-y-2">{raffles.map((raffle) => <button key={raffle.id} onClick={() => { setSelectedId(raffle.id); setPreview(null); }} className={`block w-full rounded-xl border p-3 text-left ${selectedId === raffle.id ? 'border-amber-500' : 'border-slate-800'}`}><span className="font-semibold">{raffle.title}</span>{raffle.purpose === 'test' && <span className="ml-2 rounded bg-violet-500/20 px-2 text-xs">{t('raffle.operations.testLabel')}</span>}<small className="block text-slate-400">{t(`raffle.operations.execution.${raffle.execution_state}`)}</small></button>)}</div>
      {selected && <div className="space-y-5 rounded-2xl border border-slate-800 p-5">
        <div className="grid gap-3 sm:grid-cols-3"><div>{t('raffle.operations.scheduledLocal')}<strong className="block">{selected.scheduled_run_at ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short', timeZone: selected.timezone_name }).format(new Date(selected.scheduled_run_at)) : '—'}</strong></div><div>{t('raffle.operations.scheduledUtc')}<strong className="block">{selected.scheduled_run_at || '—'}</strong></div><div>{t('raffle.operations.retryState')}<strong className="block">{selected.retry_count}</strong></div></div>
        {selected.last_error_summary && <div className="rounded-lg border border-red-500/30 p-3">{t('raffle.operations.lastFailure')}: {selected.last_error_summary}</div>}
        <div className="flex flex-wrap gap-2"><button onClick={async () => setPreview(await raffleApi.previewEligibility(selected.id))} className="rounded-lg border border-slate-700 px-3 py-2">{t('raffle.operations.preview')}</button><button onClick={async () => setPreview(await raffleApi.freezeEligibility(selected.id))} className="rounded-lg border border-slate-700 px-3 py-2">{t('raffle.operations.freeze')}</button></div>
        {selected.purpose === 'test' && <div className="flex gap-2"><input value={testCharacter} onChange={(e) => setTestCharacter(e.target.value)} placeholder={t('raffle.operations.testCharacter')} className="min-w-0 flex-1 rounded-lg bg-slate-950 p-2" /><button onClick={async () => { if (!testCharacter.trim()) return; await raffleApi.addManualParticipant(selected.id, testCharacter.trim()); setTestCharacter(''); await refreshSelected(); }} className="rounded-lg border border-violet-500/50 px-3 py-2">{t('raffle.operations.addTestParticipant')}</button></div>}
        {preview && <div className="rounded-xl bg-slate-950 p-4"><p>{t('raffle.operations.eligibleCount', { count: preview.eligible_count })} · {t('raffle.operations.excludedCount', { count: preview.excluded_count })}</p><p className="text-xs text-slate-400">{t('raffle.operations.snapshotAt', { value: preview.cutoff_at })}</p>{stale && <p className="text-amber-300">{t('raffle.operations.staleWarning')}</p>}<ul className="mt-2 text-sm">{preview.entries.filter((entry) => !entry.is_eligible).map((entry, index) => <li key={`${entry.character_name}-${index}`}>{entry.character_name || '—'} — {entry.exclusion_code}</li>)}</ul></div>}
        {latestRun && <><div className="rounded-xl border border-blue-500/30 p-3 text-blue-200">{t('raffle.operations.privateReview')}</div><AutomaticRaffleDraw results={latestRun.results} participantNames={selected.participants.map((entry) => entry.character_name)} testMode={selected.purpose === 'test'} />
          <div className="space-y-2">{latestRun.results.map((result) => <div key={result.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 p-3"><span>{result.character_name} · {result.amount} {result.currency} · {t(`raffle.operations.delivery.${result.delivery_status}`)}</span><select value={result.delivery_status} onChange={async (e) => { await raffleApi.updateDelivery(selected.id, result.id, e.target.value as typeof result.delivery_status, e.target.value === 'disputed' || e.target.value === 'cancelled' ? t('raffle.operations.delivery.managerNote') : undefined); await refreshSelected(); }} className="rounded bg-slate-950 p-2"><option value="pending">{t('raffle.operations.delivery.pending')}</option><option value="delivered">{t('raffle.operations.delivery.delivered')}</option><option value="disputed">{t('raffle.operations.delivery.disputed')}</option><option value="cancelled">{t('raffle.operations.delivery.cancelled')}</option></select></div>)}</div>
          {canPublish && <div className="flex gap-2"><button onClick={async () => { await raffleApi.publish(selected.id); await refreshSelected(); }} className="rounded-lg bg-emerald-600 px-3 py-2">{t('raffle.operations.publish')}</button><button onClick={async () => { await raffleApi.unpublish(selected.id); await refreshSelected(); }} className="rounded-lg border border-slate-700 px-3 py-2">{t('raffle.operations.unpublish')}</button></div>}
          <div className="space-y-2 rounded-xl border border-slate-800 p-4"><h3>{t('raffle.operations.rerunTitle')}</h3>{(['second', 'first'] as const).map((position) => <label key={position} className="mr-4"><input type="checkbox" checked={rerunPositions.includes(position)} onChange={() => setRerunPositions((values) => values.includes(position) ? values.filter((value) => value !== position) : [...values, position])} /> {t(`raffle.operations.${position}Place`)}</label>)}<input value={rerunReason} onChange={(e) => setRerunReason(e.target.value)} placeholder={t('raffle.operations.rerunReason')} className="block w-full rounded bg-slate-950 p-2" /><p className="text-sm text-amber-300">{t('raffle.operations.rerunWarning')}</p><button disabled={busy} onClick={performRerun} className="rounded bg-amber-500 px-3 py-2 text-slate-950">{t('raffle.operations.rerun')}</button></div>
        </>}
      </div>}
    </section>
  </div>;
}
