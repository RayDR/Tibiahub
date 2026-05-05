import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Crown, Loader2, ScrollText } from 'lucide-react';

import { questsApi } from '../services/api';
import type { QuestDetail } from '../types';

export default function QuestDetailPage() {
  const { questId } = useParams<{ questId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      if (!questId) return;
      try {
        setLoading(true);
        setError(null);
        setQuest(await questsApi.getById(Number(questId), controller.signal));
      } catch (err: any) {
        setError(err?.response?.data?.detail || err?.message || 'Quest not found');
      } finally {
        setLoading(false);
      }
    };
    void run();
    return () => controller.abort();
  }, [questId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-amber-500">
        <Loader2 className="animate-spin" size={42} />
      </div>
    );
  }

  if (!quest || error) {
    return (
      <div className="mx-auto mt-20 max-w-3xl rounded-2xl border border-red-500/20 bg-red-950/20 p-6 text-red-100">
        <div className="mb-3 text-lg font-semibold">Quest detail unavailable</div>
        <p className="text-sm text-red-200/80">{error || 'Quest not found'}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-20 pt-28">
      <div className="container mx-auto px-4">
        <button onClick={() => navigate('/cyclopedia')} className="mb-6 flex items-center gap-2 text-slate-400 hover:text-white">
          <ArrowLeft size={18} /> Back to Cyclopedia
        </button>

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <div className="mb-4 flex items-center gap-3 text-amber-300">
            <ScrollText size={24} />
            <h1 className="text-3xl font-bold text-white">{quest.name}</h1>
          </div>

          <p className="mb-4 text-slate-300">{quest.description || 'Description not available.'}</p>

          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">Min level: {quest.min_level ?? 'N/A'}</div>
            <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">Max level: {quest.max_level ?? 'N/A'}</div>
            <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">XP reward: {quest.experience_reward ?? 'N/A'}</div>
            <div className="rounded-lg bg-slate-950/60 p-3 text-slate-300">NPC: {quest.npc || 'Unknown'}</div>
          </div>

          <div className="mb-6">
            <h2 className="mb-2 text-lg font-semibold text-amber-200">Requirements</h2>
            {quest.requirements.length > 0 ? (
              <ul className="space-y-2">
                {quest.requirements.map((item, index) => (
                  <li key={`${item}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No explicit requirements available.</p>
            )}
          </div>

          <div>
            <h2 className="mb-2 text-lg font-semibold text-amber-200">Related Creatures / Bosses</h2>
            {quest.related_creatures.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {quest.related_creatures.map((creature) => (
                  <Link to={`/creatures/${creature.creature_slug || creature.creature_id}`} key={creature.creature_id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 hover:border-amber-500/40">
                    <div className="mb-1 flex items-center gap-2 text-slate-100">
                      {creature.is_boss ? <Crown size={14} className="text-red-300" /> : null}
                      <span className="font-semibold">{creature.creature_name}</span>
                    </div>
                    <div className="text-xs text-slate-400">{creature.classification || 'Unknown classification'}</div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No related creatures found in local data.</p>
            )}
          </div>

          {quest.source_url && (
            <a href={quest.source_url} target="_blank" rel="noreferrer" className="mt-6 inline-block text-sm text-amber-400 hover:text-amber-300">
              Open source page
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
