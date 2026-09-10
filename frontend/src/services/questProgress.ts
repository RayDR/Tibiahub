import api from './api';

export type QuestProgressStatus = 'not_started' | 'in_progress' | 'completed';

export interface QuestProgressState {
  quest_id: number;
  character_id: number;
  status: QuestProgressStatus;
  completed: boolean;
  completed_mission_ids: string[];
  completed_steps: number;
  total_steps: number;
  current_mission_id?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
}

export type QuestCompletionState = QuestProgressState;

export interface QuestProgressUpdate {
  completed?: boolean;
  status?: QuestProgressStatus;
  completed_mission_ids?: string[];
}

export const questProgressApi = {
  get: async (identifier: string | number, characterId: number, signal?: AbortSignal): Promise<QuestProgressState> => (
    await api.get(`/quest-progress/${encodeURIComponent(identifier)}`, {
      params: { character_id: characterId },
      signal,
    })
  ).data,

  list: async (characterId: number, signal?: AbortSignal): Promise<QuestProgressState[]> => (
    await api.get('/quest-progress', {
      params: { character_id: characterId },
      signal,
    })
  ).data,

  set: async (
    identifier: string | number,
    characterId: number,
    update: boolean | QuestProgressUpdate,
  ): Promise<QuestProgressState> => (
    await api.put(`/quest-progress/${encodeURIComponent(identifier)}`,
      typeof update === 'boolean' ? { completed: update } : update,
      { params: { character_id: characterId } },
    )
  ).data,
};
