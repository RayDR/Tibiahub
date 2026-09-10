import { Check, Circle, Loader2, RotateCcw, Trophy } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { useActiveCharacter } from '../../context/ActiveCharacterContext';
import { useQuestProgress } from '../../context/QuestProgressContext';
import { questsApi } from '../../services/api';
import type { QuestMission } from '../../types';
import QuestProgressMeter from './QuestProgressMeter';

export default function QuestCompletionControl({
  questId,
  questSlug,
}: {
  questId: number;
  questSlug?: string;
}) {
  const { t } = useTranslation();
  const { activeCharacter } = useActiveCharacter();
  const { getProgress, updateProgress } = useQuestProgress();
  const [missions, setMissions] = useState<QuestMission[]>([]);
  const [loadingMissions, setLoadingMissions] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingMissions(true);
    void questsApi.getById(questSlug || questId, controller.signal)
      .then((quest) => {
        if (!controller.signal.aborted) {
          setMissions([...quest.missions].sort((a, b) => a.sequence - b.sequence));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setMissions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingMissions(false);
      });
    return () => controller.abort();
  }, [questId, questSlug]);

  const progress = getProgress(questId, missions.length);
  const completedIds = useMemo(() => new Set(progress.completed_mission_ids), [progress.completed_mission_ids]);

  const save = async (completedMissionIds: string[], status?: 'not_started' | 'in_progress' | 'completed') => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      await updateProgress(
        questId,
        status ? { status, completed_mission_ids: completedMissionIds } : { completed_mission_ids: completedMissionIds },
        missions.length,
      );
    } catch {
      setError(t('questEnhancement.progressSaveError'));
    } finally {
      setSaving(false);
    }
  };

  const toggleMission = async (mission: QuestMission) => {
    const index = missions.findIndex((candidate) => candidate.id === mission.id);
    if (index < 0) return;
    const alreadyCompleted = completedIds.has(mission.id);
    const nextIds = alreadyCompleted
      ? missions.slice(0, index).map((candidate) => candidate.id)
      : missions.slice(0, index + 1).map((candidate) => candidate.id);
    await save(nextIds);
  };

  const completeQuest = () => save(missions.map((mission) => mission.id), 'completed');
  const resetQuest = () => save([], 'not_started');

  return (
    <section className="quest-codex__progress mt-6 overflow-hidden rounded-xl border bg-surface-raised/60" aria-label={t('questEnhancement.progress')}>
      <div className="border-b border-line p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-content-muted">{t('questEnhancement.progress')}</p>
            <p className="mt-1 text-sm text-content-secondary">
              {activeCharacter
                ? t('questEnhancement.savedFor', { character: activeCharacter.character_name })
                : t('questEnhancement.sessionOnly')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {progress.status !== 'completed' ? (
              <button type="button" onClick={() => void completeQuest()} disabled={saving || loadingMissions} className="app-button-primary app-button-sm min-h-10">
                {saving ? <Loader2 className="size-4 animate-spin" /> : <Trophy className="size-4" />}
                {t('questEnhancement.markComplete')}
              </button>
            ) : null}
            {progress.status !== 'not_started' ? (
              <button type="button" onClick={() => void resetQuest()} disabled={saving} className="app-button-ghost app-button-sm min-h-10">
                <RotateCcw className="size-4" />
                {t('questEnhancement.resetProgress')}
              </button>
            ) : null}
          </div>
        </div>

        <div className="mt-4">
          <QuestProgressMeter
            completed={progress.completed_steps}
            total={missions.length || progress.total_steps}
            status={progress.status}
          />
        </div>
      </div>

      {missions.length ? (
        <ol className="divide-y divide-line">
          {missions.map((mission, index) => {
            const completed = completedIds.has(mission.id) || progress.status === 'completed';
            const current = !completed && (
              progress.current_mission_id === mission.id
              || (progress.status === 'not_started' && index === 0)
              || (!progress.current_mission_id && index === progress.completed_steps)
            );
            return (
              <li key={mission.id}>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void toggleMission(mission)}
                  className={`flex min-h-12 w-full items-center gap-3 px-4 py-3 text-left transition sm:px-5 ${current ? 'bg-primary/10' : 'hover:bg-surface-hover'}`}
                  aria-pressed={completed}
                >
                  <span className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs font-bold ${completed ? 'border-success/50 bg-success/15 text-success' : current ? 'border-primary/60 bg-primary/15 text-primary' : 'border-line text-content-muted'}`}>
                    {completed ? <Check className="size-4" /> : current ? mission.sequence : <Circle className="size-3.5" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={`block text-sm font-semibold ${completed ? 'text-content-secondary' : 'text-content-primary'}`}>{mission.title}</span>
                    {current ? <span className="mt-0.5 block text-xs font-medium text-primary">{t('questEnhancement.currentObjective')}</span> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      ) : loadingMissions ? (
        <div className="flex min-h-20 items-center justify-center text-content-muted"><Loader2 className="size-4 animate-spin" /></div>
      ) : null}

      {!activeCharacter ? <p className="border-t border-line px-4 py-3 text-xs text-content-muted sm:px-5">{t('questEnhancement.sessionHelp')}</p> : null}
      {error ? <p className="border-t border-danger/20 bg-danger/10 px-4 py-3 text-xs text-danger sm:px-5">{error}</p> : null}
    </section>
  );
}
