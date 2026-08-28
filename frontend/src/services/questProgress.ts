import api from './api';

export interface QuestCompletionState {
  quest_id: number;
  character_id: number;
  completed: boolean;
  completed_at?: string | null;
}

export const questProgressApi = {
  get: async (identifier: string | number, characterId: number, signal?: AbortSignal): Promise<QuestCompletionState> => (
    await api.get(`/quest-progress/${encodeURIComponent(identifier)}`, {
      params: { character_id: characterId },
      signal,
    })
  ).data,

  set: async (identifier: string | number, characterId: number, completed: boolean): Promise<QuestCompletionState> => (
    await api.put(`/quest-progress/${encodeURIComponent(identifier)}`, {
      completed,
    }, {
      params: { character_id: characterId },
    })
  ).data,
};
