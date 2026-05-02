import React, { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2, Trophy, Users } from 'lucide-react';

import { raffleApi, type Raffle } from '../services/raffle';

const RafflePublicPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const raffleId = Number(id);

  const [raffle, setRaffle] = useState<Raffle | null>(null);
  const [characterName, setCharacterName] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!raffleId || Number.isNaN(raffleId)) {
        setError('Invalid raffle id');
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await raffleApi.getPublic(raffleId);
        setRaffle(data);
      } catch (loadError: any) {
        setError(loadError?.response?.data?.detail || loadError?.message || 'Failed to load raffle');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [raffleId]);

  const submitRegistration = async (event: FormEvent) => {
    event.preventDefault();
    if (!raffle) return;

    try {
      setBusy(true);
      setError(null);
      setSuccess(null);
      const updated = await raffleApi.registerPublic(raffle.id, characterName);
      setRaffle(updated);
      setCharacterName('');
      setSuccess('Character registered successfully.');
    } catch (registerError: any) {
      setError(registerError?.response?.data?.detail || registerError?.message || 'Could not register character');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-slate-300">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!raffle || error) {
    return (
      <div className="mx-auto mt-10 max-w-3xl rounded-xl border border-red-500/30 bg-red-950/30 p-6 text-red-100">
        {error || 'Raffle not found'}
      </div>
    );
  }

  return (
    <div className="min-h-screen space-y-8 pb-16 pt-10">
      <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
        <h1 className="text-3xl font-bold text-amber-200">{raffle.title}</h1>
        <p className="mt-2 text-slate-300">{raffle.description || 'Public guild raffle'}</p>
        <p className="mt-2 text-sm text-slate-500">Guild: {raffle.guild_name}</p>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={submitRegistration} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-slate-100">
            <Users className="h-5 w-5 text-amber-400" /> Register Character
          </h2>
          <p className="mb-4 text-sm text-slate-400">No login required. Character must belong to the guild.</p>
          <input
            value={characterName}
            onChange={(e) => setCharacterName(e.target.value)}
            placeholder="Character name"
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
            required
          />
          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded-xl bg-amber-500 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
          >
            {busy ? 'Registering...' : 'Register'}
          </button>
          {success && <p className="mt-3 text-sm text-emerald-300">{success}</p>}
          {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
        </form>

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h2 className="mb-3 text-xl font-semibold text-slate-100">Prizes</h2>
          <div className="space-y-2 text-sm text-slate-300">
            {raffle.prizes.map((prize) => (
              <div key={prize.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                {prize.name}: {prize.reward}
              </div>
            ))}
            {raffle.prizes.length === 0 && <div className="text-slate-500">No prizes configured.</div>}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h3 className="mb-3 text-lg font-semibold text-slate-100">Participants ({raffle.participants.length})</h3>
          <div className="max-h-72 space-y-2 overflow-y-auto pr-2 text-sm">
            {raffle.participants.map((participant) => (
              <div key={participant.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-slate-300">
                <div className="font-medium text-slate-100">{participant.character_name}</div>
                <div className="text-xs text-slate-500">Rank: {participant.guild_rank || 'Member'} · Weight: {participant.weight.toFixed(1)}</div>
              </div>
            ))}
            {raffle.participants.length === 0 && <div className="text-slate-500">No participants yet.</div>}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-100">
            <Trophy className="h-5 w-5 text-amber-400" /> Winners
          </h3>
          <div className="space-y-2 text-sm text-slate-300">
            {raffle.current_winners.map((winner) => (
              <div key={winner.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                <div className="font-medium text-slate-100">{winner.prize_name}</div>
                <div>{winner.character_name}</div>
              </div>
            ))}
            {raffle.current_winners.length === 0 && <div className="text-slate-500">Winners not drawn yet.</div>}
          </div>
        </div>
      </section>
    </div>
  );
};

export default RafflePublicPage;
