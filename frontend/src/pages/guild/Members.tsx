import { useEffect, useMemo, useState } from 'react';
import { Loader2, RefreshCcw, Users } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { GuildMember, guildApi } from '../../services/guild';
import { useGuildContext } from '../../utils/guildContext';

export default function GuildMembersPage() {
  const { user } = useAuth();
  const guildName = useGuildContext(user);

  const [members, setMembers] = useState<GuildMember[]>([]);
  const [source, setSource] = useState<'live' | 'snapshot'>('snapshot');
  const [loading, setLoading] = useState(true);
  const [busySync, setBusySync] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSync = user?.is_superuser || ['leader', 'vice leader'].includes((user?.guild_rank || '').toLowerCase());

  const sortedMembers = useMemo(() => {
    return [...members].sort((a, b) => (b.level || 0) - (a.level || 0));
  }, [members]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        if (!guildName) throw new Error('Missing guild context');
        const payload = await guildApi.getGuildMembers(guildName);
        setMembers(payload.members);
        setSource(payload.source);
      } catch (loadError: any) {
        setError(loadError?.response?.data?.detail || loadError?.message || 'Failed to load guild members');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [guildName]);

  const forceSync = async () => {
    try {
      setBusySync(true);
      setError(null);
      if (!guildName) throw new Error('Missing guild context');
      const payload = await guildApi.syncGuildMembers(guildName);
      setMembers(payload.members);
      setSource(payload.source);
    } catch (syncError: any) {
      setError(syncError?.response?.data?.detail || syncError?.message || 'Guild sync failed');
    } finally {
      setBusySync(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading guild members...
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-100">
            <Users className="h-5 w-5 text-amber-400" /> Guild Members
          </h1>
          {canSync && (
            <button
              onClick={() => void forceSync()}
              disabled={busySync}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-50"
            >
              <RefreshCcw className={`h-4 w-4 ${busySync ? 'animate-spin' : ''}`} /> Refresh now
            </button>
          )}
        </div>
        <p className="text-sm text-slate-400">Guild: {guildName}</p>
        <p className="mt-1 text-xs text-slate-500">Source: {source === 'live' ? 'Live guild roster' : 'Saved guild snapshot'}</p>
        {error && <p className="mt-2 text-sm text-red-300">{error}</p>}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
        <div className="grid grid-cols-[2fr_1fr_1.5fr_1.5fr_2fr] gap-2 border-b border-slate-800 bg-slate-950/60 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <div>Character</div>
          <div>Level</div>
          <div>Vocation</div>
          <div>Rank</div>
          <div>Last Login</div>
        </div>
        <div className="max-h-[60vh] overflow-y-auto">
          {sortedMembers.map((member) => (
            <div key={`${member.character_name}-${member.snapshot_at}`} className="grid grid-cols-[2fr_1fr_1.5fr_1.5fr_2fr] gap-2 border-b border-slate-800/60 px-4 py-3 text-sm text-slate-300">
              <div className="font-medium text-slate-100">{member.character_name}</div>
              <div>{member.level ?? 'N/A'}</div>
              <div>{member.vocation || 'Unknown'}</div>
              <div>{member.rank || member.role || 'Member'}</div>
              <div className="text-xs text-slate-500">{member.last_login || 'Unknown'}</div>
            </div>
          ))}
          {sortedMembers.length === 0 && (
            <div className="px-4 py-6 text-sm text-slate-500">No members available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
