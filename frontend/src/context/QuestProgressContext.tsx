import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { useActiveCharacter } from './ActiveCharacterContext';
import { useAuth } from './AuthContext';
import {
  localQuestProgress,
  LOCAL_QUEST_PROGRESS_EVENT,
  type LocalQuestProgress,
} from '../services/localQuestProgress';
import {
  questProgressApi,
  type QuestProgressState,
  type QuestProgressStatus,
  type QuestProgressUpdate,
} from '../services/questProgress';

export interface QuestProgressView {
  quest_id: number;
  character_id?: number | null;
  status: QuestProgressStatus;
  completed: boolean;
  completed_mission_ids: string[];
  completed_steps: number;
  total_steps: number;
  current_mission_id?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  is_local: boolean;
}

interface QuestProgressContextValue {
  loading: boolean;
  syncingLocal: boolean;
  pendingLocalCount: number;
  getProgress: (questId: number, totalSteps?: number) => QuestProgressView;
  updateProgress: (
    questId: number,
    update: QuestProgressUpdate,
    totalSteps?: number,
  ) => Promise<QuestProgressView>;
  refreshProgress: () => Promise<void>;
  syncLocalToActiveCharacter: () => Promise<number>;
}

const QuestProgressContext = createContext<QuestProgressContextValue | undefined>(undefined);

function remoteView(progress: QuestProgressState): QuestProgressView {
  return { ...progress, is_local: false };
}

function localView(progress: LocalQuestProgress): QuestProgressView {
  return {
    quest_id: progress.quest_id,
    character_id: null,
    status: progress.status,
    completed: progress.status === 'completed',
    completed_mission_ids: progress.completed_mission_ids,
    completed_steps: progress.status === 'completed'
      ? progress.total_steps
      : progress.completed_mission_ids.length,
    total_steps: progress.total_steps,
    current_mission_id: null,
    completed_at: null,
    updated_at: progress.updated_at,
    is_local: true,
  };
}

function emptyView(questId: number, totalSteps = 0, isLocal = false): QuestProgressView {
  return {
    quest_id: questId,
    character_id: null,
    status: 'not_started',
    completed: false,
    completed_mission_ids: [],
    completed_steps: 0,
    total_steps: totalSteps,
    current_mission_id: null,
    completed_at: null,
    updated_at: null,
    is_local: isLocal,
  };
}

function deriveLocalStatus(update: QuestProgressUpdate, totalSteps: number): QuestProgressStatus {
  if (update.status) return update.status;
  if (update.completed === true) return 'completed';
  if (update.completed === false) return 'not_started';
  const completed = update.completed_mission_ids?.length || 0;
  if (totalSteps > 0 && completed >= totalSteps) return 'completed';
  return completed > 0 ? 'in_progress' : 'not_started';
}

export function QuestProgressProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { activeCharacterId, loading: characterLoading } = useActiveCharacter();
  const [remoteProgress, setRemoteProgress] = useState<Record<number, QuestProgressState>>({});
  const [localProgress, setLocalProgress] = useState<Record<number, LocalQuestProgress>>({});
  const [loading, setLoading] = useState(false);
  const [syncingLocal, setSyncingLocal] = useState(false);

  const reloadLocal = useCallback(() => {
    const next: Record<number, LocalQuestProgress> = {};
    for (const progress of localQuestProgress.list()) next[progress.quest_id] = progress;
    setLocalProgress(next);
  }, []);

  useEffect(() => {
    reloadLocal();
    window.addEventListener(LOCAL_QUEST_PROGRESS_EVENT, reloadLocal);
    return () => window.removeEventListener(LOCAL_QUEST_PROGRESS_EVENT, reloadLocal);
  }, [reloadLocal]);

  const refreshProgress = useCallback(async () => {
    if (!isAuthenticated || activeCharacterId == null) {
      setRemoteProgress({});
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const rows = await questProgressApi.list(activeCharacterId);
      const next: Record<number, QuestProgressState> = {};
      for (const row of rows) next[row.quest_id] = row;
      setRemoteProgress(next);
    } finally {
      setLoading(false);
    }
  }, [activeCharacterId, isAuthenticated]);

  useEffect(() => {
    if (characterLoading) return;
    const controller = new AbortController();
    if (!isAuthenticated || activeCharacterId == null) {
      setRemoteProgress({});
      setLoading(false);
      return () => controller.abort();
    }

    setLoading(true);
    void questProgressApi.list(activeCharacterId, controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return;
        const next: Record<number, QuestProgressState> = {};
        for (const row of rows) next[row.quest_id] = row;
        setRemoteProgress(next);
      })
      .catch(() => {
        if (!controller.signal.aborted) setRemoteProgress({});
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [activeCharacterId, characterLoading, isAuthenticated]);

  const getProgress = useCallback((questId: number, totalSteps = 0): QuestProgressView => {
    if (isAuthenticated && activeCharacterId != null) {
      const remote = remoteProgress[questId];
      if (remote) return remoteView(remote);
      return emptyView(questId, totalSteps, false);
    }

    const local = localProgress[questId];
    if (local) return localView(local);
    return emptyView(questId, totalSteps, true);
  }, [activeCharacterId, isAuthenticated, localProgress, remoteProgress]);

  const updateProgress = useCallback(async (
    questId: number,
    update: QuestProgressUpdate,
    totalSteps = 0,
  ): Promise<QuestProgressView> => {
    if (isAuthenticated && activeCharacterId != null) {
      const next = await questProgressApi.set(questId, activeCharacterId, update);
      setRemoteProgress((current) => {
        if (next.status === 'not_started') {
          const copy = { ...current };
          delete copy[questId];
          return copy;
        }
        return { ...current, [questId]: next };
      });
      return remoteView(next);
    }

    const status = deriveLocalStatus(update, totalSteps);
    if (status === 'not_started') {
      localQuestProgress.remove(questId);
      return emptyView(questId, totalSteps, true);
    }

    const current = localProgress[questId];
    const completedMissionIds = update.completed_mission_ids
      ?? current?.completed_mission_ids
      ?? [];
    const saved = localQuestProgress.set({
      quest_id: questId,
      status,
      completed_mission_ids: completedMissionIds,
      total_steps: Math.max(totalSteps, current?.total_steps || 0),
    });
    return localView(saved);
  }, [activeCharacterId, isAuthenticated, localProgress]);

  const syncLocalToActiveCharacter = useCallback(async (): Promise<number> => {
    if (!isAuthenticated || activeCharacterId == null) return 0;
    const pending = localQuestProgress.list();
    if (!pending.length) return 0;

    setSyncingLocal(true);
    let savedCount = 0;
    try {
      for (const local of pending) {
        const remote = remoteProgress[local.quest_id];
        if (remote?.status === 'completed') {
          localQuestProgress.remove(local.quest_id);
          savedCount += 1;
          continue;
        }

        const update: QuestProgressUpdate = local.status === 'completed'
          ? { status: 'completed' }
          : {
            completed_mission_ids: [
              ...new Set([
                ...(remote?.completed_mission_ids || []),
                ...local.completed_mission_ids,
              ]),
            ],
          };
        const next = await questProgressApi.set(local.quest_id, activeCharacterId, update);
        setRemoteProgress((current) => ({ ...current, [local.quest_id]: next }));
        localQuestProgress.remove(local.quest_id);
        savedCount += 1;
      }
      return savedCount;
    } finally {
      setSyncingLocal(false);
    }
  }, [activeCharacterId, isAuthenticated, remoteProgress]);

  const value = useMemo<QuestProgressContextValue>(() => ({
    loading,
    syncingLocal,
    pendingLocalCount: Object.keys(localProgress).length,
    getProgress,
    updateProgress,
    refreshProgress,
    syncLocalToActiveCharacter,
  }), [getProgress, loading, localProgress, refreshProgress, syncLocalToActiveCharacter, syncingLocal, updateProgress]);

  return <QuestProgressContext.Provider value={value}>{children}</QuestProgressContext.Provider>;
}

export function useQuestProgress(): QuestProgressContextValue {
  const context = useContext(QuestProgressContext);
  if (!context) throw new Error('useQuestProgress must be used within QuestProgressProvider');
  return context;
}
