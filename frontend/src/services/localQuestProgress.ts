import type { QuestProgressStatus } from './questProgress';

const STORAGE_KEY = 'tibiahub:quest-progress:local:v1';
export const LOCAL_QUEST_PROGRESS_EVENT = 'tibiahub:local-quest-progress-changed';

export interface LocalQuestProgress {
  quest_id: number;
  status: QuestProgressStatus;
  completed_mission_ids: string[];
  total_steps: number;
  updated_at: string;
}

type StoredProgress = Record<string, LocalQuestProgress>;

function readAll(): StoredProgress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredProgress;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeAll(next: StoredProgress): void {
  try {
    if (Object.keys(next).length === 0) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(LOCAL_QUEST_PROGRESS_EVENT));
  } catch {
    // Local progress is best-effort when browser storage is unavailable.
  }
}

export const localQuestProgress = {
  list(): LocalQuestProgress[] {
    return Object.values(readAll()).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  },

  get(questId: number): LocalQuestProgress | null {
    return readAll()[String(questId)] || null;
  },

  set(progress: Omit<LocalQuestProgress, 'updated_at'>): LocalQuestProgress {
    const next: LocalQuestProgress = {
      ...progress,
      completed_mission_ids: [...new Set(progress.completed_mission_ids)],
      updated_at: new Date().toISOString(),
    };
    const all = readAll();
    all[String(progress.quest_id)] = next;
    writeAll(all);
    return next;
  },

  remove(questId: number): void {
    const all = readAll();
    if (!(String(questId) in all)) return;
    delete all[String(questId)];
    writeAll(all);
  },

  clear(): void {
    writeAll({});
  },
};
