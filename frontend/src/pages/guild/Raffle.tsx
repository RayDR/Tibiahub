import { FormEvent, useEffect, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faDice,
  faFlask,
  faFloppyDisk,
  faGift,
  faLock,
  faPen,
  faRotate,
  faRotateLeft,
  faShareNodes,
  faSpinner,
  faTrash,
  faTriangleExclamation,
  faTrophy,
  faUserMinus,
  faUserPlus,
  faUsers,
} from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { guildApi } from '../../services/guild';
import { guildManagementApi } from '../../services/guildManagement';
import { Raffle, RaffleAccessMode, RaffleSimulation, RaffleStatus, raffleApi } from '../../services/raffle';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type Tab = 'overview' | 'participants' | 'prizes' | 'winners' | 'admin';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  open: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  closed: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  completed: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  cancelled: 'bg-red-500/15 text-red-300 border-red-500/30',
  deleted: 'bg-red-600/15 text-red-400 border-red-600/30',
};

const ACCESS_MODE_COLORS: Record<string, string> = {
  guild_only: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  world_only: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  public: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
};

interface TooltipButtonProps {
  onClick?: () => void;
  tooltip: string;
  disabled?: boolean;
  danger?: boolean;
  primary?: boolean;
  children: React.ReactNode;
  type?: 'button' | 'submit';
  'aria-label'?: string;
}

function IconBtn({ onClick, tooltip, disabled, danger, primary, children, type = 'button', 'aria-label': ariaLabel }: TooltipButtonProps) {
  const base = 'group relative inline-flex items-center justify-center rounded-xl border p-2 transition disabled:opacity-40';
  const variant = danger
    ? 'border-red-500/40 text-red-300 hover:bg-red-500/10'
    : primary
    ? 'border-amber-500 bg-amber-500 text-slate-950 hover:bg-amber-400'
    : 'border-slate-700 text-slate-300 hover:border-slate-500 hover:text-slate-100';

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel ?? tooltip}
      className={`${base} ${variant}`}
    >
      {children}
      <span className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-800 px-2 py-1 text-xs text-slate-200 opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {tooltip}
      </span>
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const color = STATUS_COLORS[status] ?? STATUS_COLORS.draft;
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {t(`raffle.statusBadge.${status}`, status)}
    </span>
  );
}

function AccessModeBadge({ accessMode }: { accessMode: string }) {
  const { t } = useTranslation();
  const color = ACCESS_MODE_COLORS[accessMode] ?? ACCESS_MODE_COLORS.guild_only;
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {t(`raffle.accessModes.${accessMode}`, accessMode)}
    </span>
  );
}

const emptyPrize = { name: '', reward: '' };

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RafflePage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useTranslation();

  const [raffles, setRaffles] = useState<Raffle[]>([]);
  const [selectedRaffleId, setSelectedRaffleId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [rafflesEnabled, setRafflesEnabled] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [simulation, setSimulation] = useState<RaffleSimulation | null>(null);

  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    guild_name: string;
    access_mode: RaffleAccessMode;
    show_participants: boolean;
    prizes: Array<{ name: string; reward: string }>;
  }>({
    title: '',
    description: '',
    guild_name: '',
    access_mode: 'guild_only' as const,
    show_participants: true,
    prizes: [
      { name: '', reward: '' },
      { name: '', reward: '' },
      { name: '', reward: '' },
    ],
  });
  const [newPrize, setNewPrize] = useState(emptyPrize);
  const [rerunReason, setRerunReason] = useState('');
  const [manualCharacter, setManualCharacter] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [availableGuilds, setAvailableGuilds] = useState<string[]>([]);

  const isLeader = ['leader', 'vice leader', 'guild leader', 'alpha warbringer', 'bloodhowl marshal'].includes(
    (user?.guild_rank || '').toLowerCase(),
  );
  const canManage = Boolean(user?.is_superuser || isLeader);

  useEffect(() => { void loadRaffles(); }, []);
  useEffect(() => {
    void (async () => {
      try {
        const flags = await guildApi.getFeatureFlags();
        setRafflesEnabled(flags.guild_raffles_enabled);
      } catch { setRafflesEnabled(true); }
    })();
  }, []);
  useEffect(() => {
    if (!canManage) return;
    void (async () => {
      try { setAvailableGuilds(await guildManagementApi.getGuilds()); }
      catch { setAvailableGuilds([]); }
    })();
  }, [canManage]);
  useEffect(() => {
    if (!createForm.guild_name && user?.guild_name) {
      setCreateForm((c) => ({ ...c, guild_name: user.guild_name || '' }));
    }
  }, [user?.guild_name, createForm.guild_name]);

  const selectedRaffle = raffles.find((r) => r.id === selectedRaffleId) ?? null;

  async function loadRaffles(targetId?: number) {
    setLoading(true);
    try {
      const data = await raffleApi.list();
      setRaffles(data);
      if (data.length > 0) {
        setSelectedRaffleId(targetId ?? selectedRaffleId ?? data[0].id);
      } else {
        setSelectedRaffleId(null);
      }
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load raffles');
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedRaffle(raffleId: number) {
    const updated = await raffleApi.get(raffleId);
    setRaffles((curr) => curr.map((r) => (r.id === raffleId ? updated : r)));
    setSelectedRaffleId(raffleId);
  }

  async function handleCreateRaffle(event: FormEvent) {
    event.preventDefault();
    setBusyAction('create');
    try {
      const raffle = await raffleApi.create({
        title: createForm.title,
        description: createForm.description || undefined,
        guild_name: createForm.guild_name,
        access_mode: createForm.access_mode,
        show_participants: createForm.show_participants,
        prizes: createForm.prizes.filter((p) => p.name && p.reward),
      });
      toast.success(t('raffle.create.success'));
      setCreateForm({
        title: '', description: '', guild_name: '', access_mode: 'guild_only', show_participants: true,
        prizes: [
          { name: '', reward: '' },
          { name: '', reward: '' },
          { name: '', reward: '' },
        ],
      });
      await loadRaffles(raffle.id);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.create.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSyncParticipants() {
    if (!selectedRaffle) return;
    setBusyAction('sync');
    try {
      const updated = await raffleApi.syncParticipants(selectedRaffle.id);
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
      toast.success(t('raffle.participants.syncSuccess', { count: updated.participants.length }));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.participants.syncError'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleAddPrize(event: FormEvent) {
    event.preventDefault();
    if (!selectedRaffle) return;
    setBusyAction('prize');
    try {
      const updated = await raffleApi.addPrize(selectedRaffle.id, newPrize);
      setNewPrize(emptyPrize);
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
      toast.success(t('raffle.prizes.success'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.prizes.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDraw() {
    if (!selectedRaffle) return;
    setBusyAction('draw');
    try {
      await raffleApi.draw(selectedRaffle.id);
      await refreshSelectedRaffle(selectedRaffle.id);
      setSimulation(null);
      toast.success(t('raffle.draw.success'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.draw.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSimulate() {
    if (!selectedRaffle) return;
    setBusyAction('simulate');
    try {
      const result = await raffleApi.simulate(selectedRaffle.id);
      setSimulation(result);
      setActiveTab('winners');
      toast.success(t('raffle.simulation.title'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.simulation.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRerun() {
    if (!selectedRaffle) return;
    setBusyAction('rerun');
    try {
      await raffleApi.rerun(selectedRaffle.id, rerunReason);
      setRerunReason('');
      await refreshSelectedRaffle(selectedRaffle.id);
      setSimulation(null);
      toast.success(t('raffle.rerun.success'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.rerun.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSaveRaffleSettings() {
    if (!selectedRaffle) return;
    setBusyAction('save');
    try {
      const updated = await raffleApi.update(selectedRaffle.id, {
        title: selectedRaffle.title,
        description: selectedRaffle.description,
        access_mode: selectedRaffle.access_mode,
        show_participants: selectedRaffle.show_participants,
        status: selectedRaffle.status,
        run_mode: selectedRaffle.run_mode,
        scheduled_run_at: selectedRaffle.scheduled_run_at,
        archive_after_days: selectedRaffle.archive_after_days,
      });
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
      setEditMode(false);
      toast.success(t('raffle.edit.saveSuccess'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.edit.saveError'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleShareRaffle() {
    if (!selectedRaffle) return;
    const url = `${window.location.origin}/raffles/${selectedRaffle.public_code}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t('raffle.share.success'));
    } catch {
      toast.error(t('raffle.share.error'));
    }
  }

  async function handleDeleteRaffle() {
    if (!selectedRaffle) return;
    if (!window.confirm(t('raffle.delete.confirm'))) return;
    setBusyAction('delete');
    try {
      await raffleApi.softDelete(selectedRaffle.id, 'deleted by manager');
      await loadRaffles();
      toast.success(t('raffle.delete.success'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.delete.error'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleManualParticipant() {
    if (!selectedRaffle || !manualCharacter.trim()) return;
    setBusyAction('manual');
    try {
      const updated = await raffleApi.addManualParticipant(selectedRaffle.id, manualCharacter.trim());
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
      setManualCharacter('');
      toast.success(t('raffle.participants.addSuccess'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.participants.addError'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleWeightChange(participantId: number, value: number) {
    if (!selectedRaffle) return;
    setBusyAction(`weight-${participantId}`);
    try {
      const updated = await raffleApi.updateWeightMultiplier(selectedRaffle.id, participantId, value);
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.participants.weightError'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRemoveParticipant(participantId: number) {
    if (!selectedRaffle) return;
    if (!window.confirm(t('raffle.participants.removeConfirm'))) return;
    setBusyAction(`remove-${participantId}`);
    try {
      const updated = await raffleApi.removeParticipant(selectedRaffle.id, participantId);
      setRaffles((curr) => curr.map((r) => (r.id === updated.id ? updated : r)));
      toast.success(t('raffle.participants.removeSuccess'));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || t('raffle.participants.removeError'));
    } finally {
      setBusyAction(null);
    }
  }

  if (!canManage) {
    return (
      <div className="rounded-2xl border border-red-500/20 bg-red-950/20 p-6 text-red-100">
        <div className="mb-3 flex items-center gap-3 text-lg font-semibold">
          <FontAwesomeIcon icon={faTriangleExclamation} className="h-5 w-5" />
          {t('raffle.console.noAccess')}
        </div>
        <p className="text-sm text-red-200/80">{t('raffle.console.noAccessDesc')}</p>
      </div>
    );
  }

  if (!rafflesEnabled) {
    return (
      <div className="rounded-2xl border border-amber-500/20 bg-amber-950/20 p-6 text-amber-100">
        {t('raffle.console.disabled')}
      </div>
    );
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview',     label: t('raffle.detail.tabs.overview') },
    { id: 'participants', label: t('raffle.detail.tabs.participants') },
    { id: 'prizes',       label: t('raffle.detail.tabs.prizes') },
    { id: 'winners',      label: t('raffle.detail.tabs.winners') },
    { id: 'admin',        label: t('raffle.detail.tabs.admin') },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900/80 to-slate-950 p-6">
        <div className="flex items-center gap-3">
          <FontAwesomeIcon icon={faTrophy} className="h-6 w-6 text-amber-400" />
          <h1 className="text-2xl font-bold text-slate-100">{t('raffle.console.title')}</h1>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">{t('raffle.console.subtitle')}</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <form onSubmit={handleCreateRaffle} className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-100">
            <FontAwesomeIcon icon={faGift} className="h-4 w-4 text-amber-400" />
            {t('raffle.create.title')}
          </h2>

          <input
            value={createForm.title}
            onChange={(e) => setCreateForm((c) => ({ ...c, title: e.target.value }))}
            placeholder={t('raffle.create.titlePlaceholder')}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 outline-none focus:border-amber-500"
            required
          />

          {user?.is_superuser && availableGuilds.length > 0 ? (
            <select
              value={createForm.guild_name}
              onChange={(e) => setCreateForm((c) => ({ ...c, guild_name: e.target.value }))}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 outline-none focus:border-amber-500"
              required
            >
              <option value="">{t('raffle.create.selectGuild')}</option>
              {availableGuilds.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          ) : (
            <input
              value={createForm.guild_name}
              onChange={(e) => setCreateForm((c) => ({ ...c, guild_name: e.target.value }))}
              placeholder={t('raffle.create.guildPlaceholder')}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 outline-none focus:border-amber-500"
              required
            />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-slate-400">{t('raffle.create.accessModeLabel')}</label>
              <select
                value={createForm.access_mode}
                onChange={(e) => setCreateForm((c) => ({ ...c, access_mode: e.target.value as 'guild_only' | 'world_only' | 'public' }))}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 outline-none focus:border-amber-500"
              >
                <option value="guild_only">{t('raffle.accessModes.guild_only')}</option>
                <option value="world_only">{t('raffle.accessModes.world_only')}</option>
                <option value="public">{t('raffle.accessModes.public')}</option>
              </select>
            </div>
            <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={createForm.show_participants}
                onChange={(e) => setCreateForm((c) => ({ ...c, show_participants: e.target.checked }))}
                className="accent-amber-500"
              />
              {t('raffle.create.showParticipantsLabel')}
            </label>
          </div>

          <textarea
            value={createForm.description}
            onChange={(e) => setCreateForm((c) => ({ ...c, description: e.target.value }))}
            placeholder={t('raffle.create.descriptionPlaceholder')}
            className="min-h-20 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 outline-none focus:border-amber-500"
          />

          <div className="space-y-2">
            {createForm.prizes.map((prize, idx) => (
              <div key={idx} className="grid gap-2 sm:grid-cols-2">
                <input
                  value={prize.name}
                  onChange={(e) => setCreateForm((c) => ({
                    ...c,
                    prizes: c.prizes.map((p, i) => (i === idx ? { ...p, name: e.target.value } : p)),
                  }))}
                  placeholder={`${t('raffle.create.prizeName')} ${idx + 1}`}
                  className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                />
                <input
                  value={prize.reward}
                  onChange={(e) => setCreateForm((c) => ({
                    ...c,
                    prizes: c.prizes.map((p, i) => (i === idx ? { ...p, reward: e.target.value } : p)),
                  }))}
                  placeholder={t('raffle.create.prizeReward')}
                  className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                />
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={busyAction === 'create'}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-amber-400 disabled:opacity-50"
          >
            {busyAction === 'create' ? (
              <><FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> {t('raffle.create.submitting')}</>
            ) : (
              <><FontAwesomeIcon icon={faGift} className="h-4 w-4" /> {t('raffle.create.submit')}</>
            )}
          </button>
        </form>

        <div className="space-y-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-100">{t('raffle.list.title')}</h2>
              <IconBtn onClick={() => void loadRaffles()} tooltip={t('raffle.list.refresh')} disabled={loading}>
                <FontAwesomeIcon icon={faRotate} className="h-4 w-4" />
              </IconBtn>
            </div>

            {loading ? (
              <div className="flex items-center gap-3 text-slate-400">
                <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> {t('raffle.list.refresh')}...
              </div>
            ) : raffles.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700 py-8 text-center text-sm text-slate-500">
                {t('raffle.list.empty')}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {raffles.map((raffle) => (
                  <button
                    key={raffle.id}
                    onClick={() => { setSelectedRaffleId(raffle.id); setActiveTab('overview'); setSimulation(null); }}
                    className={`rounded-xl border p-4 text-left transition ${
                      selectedRaffleId === raffle.id
                        ? 'border-amber-500 bg-amber-500/10'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'
                    }`}
                  >
                    <div className="mb-1.5 flex items-start justify-between gap-2">
                      <div className="truncate text-base font-semibold text-slate-100">{raffle.title}</div>
                      <StatusBadge status={raffle.status} />
                    </div>
                    <div className="text-xs uppercase tracking-wide text-slate-500">{raffle.guild_name}</div>
                    <div className="mt-2.5 flex flex-wrap gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><FontAwesomeIcon icon={faUsers} className="h-3 w-3" />{raffle.participant_count} {t('raffle.list.participants')}</span>
                      <span className="flex items-center gap-1"><FontAwesomeIcon icon={faGift} className="h-3 w-3" />{raffle.prizes.length} {t('raffle.list.prizes')}</span>
                      <span>{t('raffle.list.run')} {raffle.current_run_number}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedRaffle && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70">
              <div className="flex flex-col gap-3 border-b border-slate-800 p-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-bold text-slate-100">{selectedRaffle.title}</h2>
                    <StatusBadge status={selectedRaffle.status} />
                    <AccessModeBadge accessMode={selectedRaffle.access_mode} />
                  </div>
                  <p className="mt-1 text-sm text-slate-400">
                    {selectedRaffle.description || t('raffle.detail.noDescription')}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {t('raffle.detail.guild')}: {selectedRaffle.guild_name}
                    <> &middot; {t('raffle.detail.accessMode')}: {t(`raffle.accessModes.${selectedRaffle.access_mode}`)}</>
                    {selectedRaffle.rerun_count > 0 && (
                      <> &middot; {t('raffle.detail.reruns')}: {selectedRaffle.rerun_count}</>
                    )}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <IconBtn onClick={() => void handleShareRaffle()} tooltip={t('raffle.actions.share')} disabled={busyAction === 'share'}>
                    {busyAction === 'share' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faShareNodes} className="h-4 w-4" />}
                  </IconBtn>
                  <IconBtn onClick={() => setEditMode((v) => !v)} tooltip={editMode ? t('raffle.actions.closeEdit') : t('raffle.actions.edit')}>
                    {editMode ? <FontAwesomeIcon icon={faLock} className="h-4 w-4" /> : <FontAwesomeIcon icon={faPen} className="h-4 w-4" />}
                  </IconBtn>
                  <IconBtn onClick={() => void handleSyncParticipants()} tooltip={t('raffle.actions.sync')} disabled={busyAction === 'sync'}>
                    {busyAction === 'sync' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faRotate} className="h-4 w-4" />}
                  </IconBtn>
                  <IconBtn onClick={() => void handleSimulate()} tooltip={t('raffle.actions.simulate')} disabled={busyAction === 'simulate'}>
                    {busyAction === 'simulate' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faFlask} className="h-4 w-4" />}
                  </IconBtn>
                  <IconBtn onClick={() => void handleDraw()} tooltip={t('raffle.actions.draw')} disabled={busyAction === 'draw'} primary>
                    {busyAction === 'draw' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faDice} className="h-4 w-4" />}
                  </IconBtn>
                  <IconBtn onClick={() => void handleDeleteRaffle()} tooltip={t('raffle.actions.delete')} disabled={busyAction === 'delete'} danger>
                    {busyAction === 'delete' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faTrash} className="h-4 w-4" />}
                  </IconBtn>
                </div>
              </div>

              {editMode && (
                <div className="border-b border-slate-800 bg-slate-950/40 p-5">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <div>
                      <label className="mb-1 block text-xs text-slate-400">{t('raffle.edit.titleLabel')}</label>
                      <input
                        value={selectedRaffle.title}
                        onChange={(e) => setRaffles((curr) => curr.map((r) => r.id === selectedRaffle.id ? { ...r, title: e.target.value } : r))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-slate-400">{t('raffle.edit.accessMode')}</label>
                      <select
                        value={selectedRaffle.access_mode}
                        onChange={(e) => setRaffles((curr) => curr.map((r) => r.id === selectedRaffle.id ? { ...r, access_mode: e.target.value as 'guild_only' | 'world_only' | 'public' } : r))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
                      >
                        <option value="guild_only">{t('raffle.accessModes.guild_only')}</option>
                        <option value="world_only">{t('raffle.accessModes.world_only')}</option>
                        <option value="public">{t('raffle.accessModes.public')}</option>
                      </select>
                      <p className="mt-1 text-xs text-slate-500">
                        {selectedRaffle.access_mode === 'guild_only' && t('raffle.edit.accessModeHelpGuild')}
                        {selectedRaffle.access_mode === 'world_only' && t('raffle.edit.accessModeHelpWorld')}
                        {selectedRaffle.access_mode === 'public' && t('raffle.edit.accessModeHelpPublic')}
                      </p>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-slate-400">{t('raffle.edit.statusLabel')}</label>
                      <select
                        value={selectedRaffle.status}
                        onChange={(e) => setRaffles((curr) => curr.map((r) => r.id === selectedRaffle.id ? { ...r, status: e.target.value as RaffleStatus } : r))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
                      >
                        <option value="draft">{t('raffle.edit.statusDraft')}</option>
                        <option value="open">{t('raffle.edit.statusOpen')}</option>
                        <option value="closed">{t('raffle.edit.statusClosed')}</option>
                        <option value="completed">{t('raffle.edit.statusCompleted')}</option>
                        <option value="cancelled">{t('raffle.edit.statusCancelled')}</option>
                      </select>
                    </div>
                    <label className="flex items-center gap-2 text-sm text-slate-300 sm:col-span-2 lg:col-span-3">
                      <input type="checkbox" checked={selectedRaffle.show_participants}
                        onChange={(e) => setRaffles((curr) => curr.map((r) => r.id === selectedRaffle.id ? { ...r, show_participants: e.target.checked } : r))}
                        className="accent-amber-500"
                      />
                      {selectedRaffle.show_participants ? t('raffle.edit.showParticipantsEnabled') : t('raffle.edit.showParticipantsDisabled')}
                    </label>
                  </div>
                  <button
                    onClick={() => void handleSaveRaffleSettings()}
                    disabled={busyAction === 'save'}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
                  >
                    {busyAction === 'save' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faFloppyDisk} className="h-4 w-4" />}
                    {busyAction === 'save' ? t('raffle.actionLabels.saving') : t('raffle.actions.save')}
                  </button>
                </div>
              )}

              <div className="flex overflow-x-auto border-b border-slate-800">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium transition ${
                      activeTab === tab.id
                        ? 'border-amber-500 text-amber-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                    {tab.id === 'participants' && selectedRaffle.participants.length > 0 && (
                      <span className="ml-1.5 rounded-full bg-slate-700 px-1.5 py-0.5 text-xs">{selectedRaffle.participants.length}</span>
                    )}
                    {tab.id === 'prizes' && selectedRaffle.prizes.length > 0 && (
                      <span className="ml-1.5 rounded-full bg-slate-700 px-1.5 py-0.5 text-xs">{selectedRaffle.prizes.length}</span>
                    )}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === 'overview' && (
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center">
                      <div className="text-2xl font-bold text-amber-300">{selectedRaffle.participant_count}</div>
                      <div className="mt-1 text-xs text-slate-400">{t('raffle.detail.tabs.participants')}</div>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center">
                      <div className="text-2xl font-bold text-amber-300">{selectedRaffle.prizes.length}</div>
                      <div className="mt-1 text-xs text-slate-400">{t('raffle.detail.tabs.prizes')}</div>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center">
                      <div className="text-2xl font-bold text-amber-300">{selectedRaffle.current_run_number}</div>
                      <div className="mt-1 text-xs text-slate-400">{t('raffle.list.run')}</div>
                    </div>
                    {selectedRaffle.prizes.length > 0 && (
                      <div className="sm:col-span-3">
                        <div className="mb-2 text-sm font-medium text-slate-300">{t('raffle.detail.tabs.prizes')}</div>
                        <div className="flex flex-wrap gap-2">
                          {selectedRaffle.prizes.map((prize) => (
                            <span key={prize.id} className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-sm text-amber-300">
                              <FontAwesomeIcon icon={faTrophy} className="h-3 w-3" />
                              <span className="font-medium">{prize.name}</span>
                              <span className="text-amber-400/70">&middot;</span>
                              <span>{prize.reward}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'participants' && (
                  <div className="space-y-4">
                    <div className="flex gap-2">
                      <input
                        value={manualCharacter}
                        onChange={(e) => setManualCharacter(e.target.value)}
                        placeholder={t('raffle.participants.characterPlaceholder')}
                        className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void handleManualParticipant(); } }}
                      />
                      <IconBtn onClick={() => void handleManualParticipant()} tooltip={t('raffle.actions.addParticipant')} disabled={busyAction === 'manual' || !manualCharacter.trim()}>
                        {busyAction === 'manual' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faUserPlus} className="h-4 w-4" />}
                      </IconBtn>
                    </div>
                    <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                      {selectedRaffle.participants.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-700 py-8 text-center text-sm text-slate-500">
                          {t('raffle.participants.empty')}
                        </div>
                      ) : (
                        selectedRaffle.participants.map((participant) => (
                          <div key={participant.id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2.5">
                            <div className="min-w-0">
                              <div className="truncate font-medium text-slate-100">{participant.character_name}</div>
                              <div className="text-xs text-slate-500">{participant.username} &middot; {participant.guild_rank || t('guild.member')}</div>
                            </div>
                            <div className="ml-3 flex shrink-0 items-center gap-2">
                              <div className="text-right text-xs text-slate-400">
                                <div className={participant.is_eligible ? 'text-emerald-400' : 'text-slate-500'}>
                                  {participant.is_eligible ? t('raffle.participants.eligible') : t('raffle.participants.ineligible')}
                                </div>
                                <div>{t('raffle.participants.weight')} {participant.weight.toFixed(1)}</div>
                              </div>
                              <div className="flex gap-0.5">
                                {[1, 2, 3, 4, 5].map((w) => (
                                  <button key={w} onClick={() => void handleWeightChange(participant.id, w)} disabled={busyAction === `weight-${participant.id}`}
                                    className={`h-6 w-5 rounded text-xs transition ${Math.round(participant.weight_multiplier || 1) === w ? 'bg-amber-500 text-slate-950' : 'border border-slate-700 text-slate-400 hover:border-amber-500/50'}`}
                                  >{w}</button>
                                ))}
                              </div>
                              <IconBtn onClick={() => void handleRemoveParticipant(participant.id)} tooltip={t('raffle.actions.removeParticipant')} disabled={busyAction === `remove-${participant.id}`} danger>
                                {busyAction === `remove-${participant.id}` ? <FontAwesomeIcon icon={faSpinner} spin className="h-3 w-3" /> : <FontAwesomeIcon icon={faUserMinus} className="h-3 w-3" />}
                              </IconBtn>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'prizes' && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                      {selectedRaffle.prizes.length === 0 ? (
                        <div className="w-full rounded-xl border border-dashed border-slate-700 py-6 text-center text-sm text-slate-500">
                          {t('raffle.prizes.empty')}
                        </div>
                      ) : (
                        selectedRaffle.prizes.map((prize) => (
                          <div key={prize.id} className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-2.5">
                            <FontAwesomeIcon icon={faGift} className="h-4 w-4 text-amber-400" />
                            <div>
                              <div className="text-sm font-medium text-amber-200">{prize.name}</div>
                              <div className="text-xs text-amber-400/70">{prize.reward}</div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <form onSubmit={handleAddPrize} className="flex gap-2">
                      <input value={newPrize.name} onChange={(e) => setNewPrize((p) => ({ ...p, name: e.target.value }))} placeholder={t('raffle.prizes.namePlaceholder')}
                        className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-amber-500" required />
                      <input value={newPrize.reward} onChange={(e) => setNewPrize((p) => ({ ...p, reward: e.target.value }))} placeholder={t('raffle.prizes.rewardPlaceholder')}
                        className="w-24 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-amber-500" required />
                      <IconBtn type="submit" tooltip={t('raffle.actions.addPrize')} disabled={busyAction === 'prize'}>
                        {busyAction === 'prize' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faGift} className="h-4 w-4" />}
                      </IconBtn>
                    </form>
                  </div>
                )}

                {activeTab === 'winners' && (
                  <div className="space-y-5">
                    {simulation && (
                      <div className="rounded-xl border border-blue-500/30 bg-blue-950/20 p-4">
                        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-blue-300">
                          <FontAwesomeIcon icon={faFlask} className="h-4 w-4" />
                          {t('raffle.simulation.title')}
                          <span className="ml-auto rounded-full bg-blue-500/20 px-2 py-0.5 text-xs">
                            {t('raffle.simulation.eligible')}: {simulation.eligible_count} &middot; {t('raffle.simulation.ineligible')}: {simulation.ineligible_count}
                          </span>
                        </div>
                        <div className="mb-3 flex flex-wrap gap-2 text-xs text-blue-200">
                          {simulation.prizes.map((prize) => (
                            <span key={prize.id} className="rounded-full border border-blue-400/20 px-2 py-1">
                              {prize.name}: {prize.reward}
                            </span>
                          ))}
                        </div>
                        <div className="mb-3 rounded-lg border border-blue-400/20 bg-slate-950/20 p-3 text-xs text-blue-100">
                          <div className="mb-1 font-semibold">{t('raffle.simulation.warnings')}</div>
                          {simulation.warnings.length > 0 ? simulation.warnings.map((warning) => (
                            <div key={warning}>{warning}</div>
                          )) : <div>{t('raffle.simulation.noWarnings')}</div>}
                        </div>
                        <div className="space-y-2">
                          {simulation.winners.map((w) => (
                            <div key={w.id} className="flex items-center justify-between rounded-lg border border-blue-500/20 px-3 py-2 text-sm">
                              <div>
                                <span className="font-medium text-blue-200">{w.character_name}</span>
                                <span className="ml-1 text-blue-400/60">&middot; {w.username}</span>
                              </div>
                              <div className="text-right text-blue-300">
                                <div className="font-medium">{w.prize_name}</div>
                                <div className="text-xs text-blue-400/60">{w.reward}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-200">
                        <FontAwesomeIcon icon={faTrophy} className="h-4 w-4 text-amber-400" />
                        {t('raffle.winners.title')}
                      </div>
                      <div className="space-y-2">
                        {selectedRaffle.current_winners.length === 0 ? (
                          <div className="text-sm text-slate-500">{t('raffle.winners.empty')}</div>
                        ) : (
                          selectedRaffle.current_winners.map((winner) => (
                            <div key={winner.id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
                              <div>
                                <div className="font-medium text-slate-100">{winner.character_name}</div>
                                <div className="text-xs text-slate-500">{winner.username}</div>
                              </div>
                              <div className="text-right">
                                <div className="text-sm font-medium text-amber-300">{winner.prize_name}</div>
                                <div className="text-xs text-amber-400/70">{winner.reward}</div>
                                <div className="text-xs text-slate-500">{t('raffle.winners.run')} {winner.run_number}</div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {selectedRaffle.history.length > 0 && (
                      <details>
                        <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-200">
                          {t('raffle.winners.history')} ({selectedRaffle.history.length})
                        </summary>
                        <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
                          {selectedRaffle.history.map((winner) => (
                            <div key={winner.id} className="rounded-lg border border-slate-800/60 px-3 py-2 text-sm text-slate-400">
                              <span className="font-medium text-slate-300">{winner.prize_name}</span>
                              {' \u2192 '}{winner.character_name}
                              <span className="ml-2 text-xs">
                                {t('raffle.winners.run')} {winner.run_number}
                                {winner.is_rerun && ` \u00b7 ${t('raffle.winners.rerun')}: ${winner.rerun_reason || t('raffle.winners.noReason')}`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {activeTab === 'admin' && (
                  <div className="space-y-5">
                    <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-red-300">
                        <FontAwesomeIcon icon={faRotateLeft} className="h-4 w-4" />
                        {t('raffle.rerun.title')}
                      </div>
                      <textarea
                        value={rerunReason}
                        onChange={(e) => setRerunReason(e.target.value)}
                        placeholder={t('raffle.rerun.reasonPlaceholder')}
                        className="min-h-20 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-red-500"
                      />
                      <button
                        onClick={() => void handleRerun()}
                        disabled={!rerunReason.trim() || busyAction === 'rerun'}
                        className="mt-3 inline-flex items-center gap-2 rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {busyAction === 'rerun' ? <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" /> : <FontAwesomeIcon icon={faRotateLeft} className="h-4 w-4" />}
                        {busyAction === 'rerun' ? t('raffle.actionLabels.rerunning') : t('raffle.actions.rerun')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
