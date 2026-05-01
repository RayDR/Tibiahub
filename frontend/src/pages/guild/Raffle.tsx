import { FormEvent, useEffect, useState } from 'react';
import { Loader2, RefreshCcw, ShieldAlert, Trophy, Users } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Raffle, raffleApi } from '../../services/raffle';

const emptyPrize = { name: '', reward: '' };

export default function RafflePage() {
  const { user } = useAuth();
  const toast = useToast();

  const [raffles, setRaffles] = useState<Raffle[]>([]);
  const [selectedRaffleId, setSelectedRaffleId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    title: '',
    description: '',
    guild_name: '',
    prizes: [
      { name: 'Premio 1', reward: '10kk' },
      { name: 'Premio 2', reward: '10kk' },
      { name: 'Premio 3', reward: '5kk' },
    ],
  });
  const [newPrize, setNewPrize] = useState(emptyPrize);
  const [rerunReason, setRerunReason] = useState('');

  useEffect(() => {
    void loadRaffles();
  }, []);

  const selectedRaffle = raffles.find((raffle) => raffle.id === selectedRaffleId) ?? null;

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
    } catch (error: any) {
      toast.error(error?.message || 'Failed to load raffles');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRaffle(event: FormEvent) {
    event.preventDefault();
    setBusyAction('create');
    try {
      const raffle = await raffleApi.create({
        title: createForm.title,
        description: createForm.description || undefined,
        guild_name: createForm.guild_name,
        prizes: createForm.prizes.filter((prize) => prize.name && prize.reward),
      });
      toast.success('Raffle created');
      setCreateForm({ title: '', description: '', guild_name: '', prizes: [
        { name: 'Premio 1', reward: '10kk' },
        { name: 'Premio 2', reward: '10kk' },
        { name: 'Premio 3', reward: '5kk' },
      ] });
      await loadRaffles(raffle.id);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to create raffle');
    } finally {
      setBusyAction(null);
    }
  }

  async function refreshSelectedRaffle(raffleId: number) {
    const updated = await raffleApi.get(raffleId);
    setRaffles((current) => current.map((raffle) => raffle.id === raffleId ? updated : raffle));
    setSelectedRaffleId(raffleId);
  }

  async function handleSyncParticipants() {
    if (!selectedRaffle) return;
    setBusyAction('sync');
    try {
      const updated = await raffleApi.syncParticipants(selectedRaffle.id);
      setRaffles((current) => current.map((raffle) => raffle.id === updated.id ? updated : raffle));
      toast.success(`Synced ${updated.participants.length} eligible accounts`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to sync participants');
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
      setRaffles((current) => current.map((raffle) => raffle.id === updated.id ? updated : raffle));
      toast.success('Prize added');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to add prize');
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
      toast.success('Raffle executed');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to execute raffle');
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
      toast.success('Raffle rerun completed');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to rerun raffle');
    } finally {
      setBusyAction(null);
    }
  }

  if (!user?.is_superuser) {
    return (
      <div className="rounded-2xl border border-red-500/20 bg-red-950/20 p-6 text-red-100">
        <div className="mb-3 flex items-center gap-3 text-lg font-semibold">
          <ShieldAlert className="h-5 w-5" />
          Admin Access Required
        </div>
        <p className="text-sm text-red-200/80">
          The guild raffle console only allows admin execution because it stores winners, rerun history, and weighted account-based selection.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h1 className="mb-2 text-3xl font-semibold text-slate-100">Guild Raffle Console</h1>
        <p className="max-w-3xl text-sm text-slate-400">
          This raffle system is account-based. It syncs local users linked to characters that currently belong to the Tibia guild, applies a 10% weight bonus to vice leaders, excludes duplicate accounts automatically, and stores full rerun history.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <form onSubmit={handleCreateRaffle} className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <h2 className="text-xl font-semibold text-slate-100">Create Raffle</h2>
          <input
            value={createForm.title}
            onChange={(event) => setCreateForm((current) => ({ ...current, title: event.target.value }))}
            placeholder="Guild weekly raffle"
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
            required
          />
          <input
            value={createForm.guild_name}
            onChange={(event) => setCreateForm((current) => ({ ...current, guild_name: event.target.value }))}
            placeholder="Bloodborne Warhowl"
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
            required
          />
          <textarea
            value={createForm.description}
            onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
            placeholder="Optional description"
            className="min-h-28 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
          />

          <div className="space-y-3">
            {createForm.prizes.map((prize, index) => (
              <div key={index} className="grid gap-3 sm:grid-cols-2">
                <input
                  value={prize.name}
                  onChange={(event) => setCreateForm((current) => ({
                    ...current,
                    prizes: current.prizes.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item),
                  }))}
                  placeholder={`Prize ${index + 1}`}
                  className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
                />
                <input
                  value={prize.reward}
                  onChange={(event) => setCreateForm((current) => ({
                    ...current,
                    prizes: current.prizes.map((item, itemIndex) => itemIndex === index ? { ...item, reward: event.target.value } : item),
                  }))}
                  placeholder="10kk"
                  className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
                />
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={busyAction === 'create'}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
          >
            {busyAction === 'create' && <Loader2 className="h-4 w-4 animate-spin" />}
            Create Raffle
          </button>
        </form>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-100">Raffles</h2>
              <button
                onClick={() => void loadRaffles()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:border-slate-500"
              >
                <RefreshCcw className="h-4 w-4" /> Refresh
              </button>
            </div>

            {loading ? (
              <div className="flex items-center gap-3 text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading raffles...
              </div>
            ) : raffles.length === 0 ? (
              <div className="text-sm text-slate-400">No raffles created yet.</div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {raffles.map((raffle) => (
                  <button
                    key={raffle.id}
                    onClick={() => setSelectedRaffleId(raffle.id)}
                    className={`rounded-xl border p-4 text-left transition ${selectedRaffleId === raffle.id ? 'border-amber-500 bg-amber-500/10' : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'}`}
                  >
                    <div className="mb-1 text-lg font-semibold text-slate-100">{raffle.title}</div>
                    <div className="text-xs uppercase tracking-wide text-slate-500">{raffle.guild_name}</div>
                    <div className="mt-3 flex gap-4 text-sm text-slate-400">
                      <span>{raffle.participants.length} participants</span>
                      <span>{raffle.prizes.length} prizes</span>
                      <span>Run {raffle.current_run_number}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedRaffle && (
            <div className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h2 className="text-2xl font-semibold text-slate-100">{selectedRaffle.title}</h2>
                  <p className="mt-1 text-sm text-slate-400">{selectedRaffle.description || 'No description provided.'}</p>
                  <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-400">
                    <span>Status: {selectedRaffle.status}</span>
                    <span>Guild: {selectedRaffle.guild_name}</span>
                    <span>Reruns: {selectedRaffle.rerun_count}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={handleSyncParticipants} disabled={busyAction === 'sync'} className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 disabled:opacity-50">
                    {busyAction === 'sync' ? 'Syncing...' : 'Sync Participants'}
                  </button>
                  <button onClick={handleDraw} disabled={busyAction === 'draw'} className="rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">
                    {busyAction === 'draw' ? 'Drawing...' : 'Execute Draw'}
                  </button>
                </div>
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="mb-3 flex items-center gap-2 text-slate-100">
                      <Users className="h-4 w-4 text-amber-400" /> Participants ({selectedRaffle.participants.length})
                    </div>
                    <div className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
                      {selectedRaffle.participants.map((participant) => (
                        <div key={participant.id} className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2 text-slate-300">
                          <div>
                            <div className="font-medium text-slate-100">{participant.character_name}</div>
                            <div className="text-xs text-slate-500">{participant.username} · {participant.guild_rank || 'Member'}</div>
                          </div>
                          <div className="text-right text-xs text-slate-400">
                            <div>weight {participant.weight.toFixed(1)}</div>
                            <div>{participant.is_eligible ? 'eligible' : 'inactive'}</div>
                          </div>
                        </div>
                      ))}
                      {selectedRaffle.participants.length === 0 && <div className="text-slate-500">No synced participants yet.</div>}
                    </div>
                  </div>

                  <form onSubmit={handleAddPrize} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="mb-3 text-slate-100">Add Prize</div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <input
                        value={newPrize.name}
                        onChange={(event) => setNewPrize((current) => ({ ...current, name: event.target.value }))}
                        placeholder="Premio 4"
                        className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                        required
                      />
                      <input
                        value={newPrize.reward}
                        onChange={(event) => setNewPrize((current) => ({ ...current, reward: event.target.value }))}
                        placeholder="2kk"
                        className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                        required
                      />
                    </div>
                    <button type="submit" disabled={busyAction === 'prize'} className="mt-3 rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 disabled:opacity-50">
                      Add Prize
                    </button>
                  </form>
                </div>

                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="mb-3 flex items-center gap-2 text-slate-100">
                      <Trophy className="h-4 w-4 text-amber-400" /> Current Winners
                    </div>
                    <div className="space-y-2 text-sm">
                      {selectedRaffle.current_winners.map((winner) => (
                        <div key={winner.id} className="rounded-lg border border-slate-800 px-3 py-3 text-slate-300">
                          <div className="font-medium text-slate-100">{winner.prize_name}: {winner.reward}</div>
                          <div>{winner.character_name} ({winner.username})</div>
                          <div className="text-xs text-slate-500">Run {winner.run_number}</div>
                        </div>
                      ))}
                      {selectedRaffle.current_winners.length === 0 && <div className="text-slate-500">No draw executed yet.</div>}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="mb-3 text-slate-100">Rerun</div>
                    <textarea
                      value={rerunReason}
                      onChange={(event) => setRerunReason(event.target.value)}
                      placeholder="Reason for rerun"
                      className="min-h-24 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-amber-500"
                    />
                    <button
                      onClick={handleRerun}
                      disabled={!rerunReason || busyAction === 'rerun'}
                      className="mt-3 rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      {busyAction === 'rerun' ? 'Rerunning...' : 'Rerun as Admin'}
                    </button>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="mb-3 text-slate-100">History</div>
                    <div className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
                      {selectedRaffle.history.map((winner) => (
                        <div key={winner.id} className="rounded-lg border border-slate-800 px-3 py-3 text-slate-300">
                          <div className="font-medium text-slate-100">{winner.prize_name}: {winner.reward}</div>
                          <div>{winner.character_name} ({winner.username})</div>
                          <div className="text-xs text-slate-500">
                            Run {winner.run_number}{winner.is_rerun ? ` · rerun · ${winner.rerun_reason || 'No reason'}` : ''}
                          </div>
                        </div>
                      ))}
                      {selectedRaffle.history.length === 0 && <div className="text-slate-500">No history yet.</div>}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
