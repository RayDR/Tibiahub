import api from './api';
import { getActiveCharacterId } from '../utils/activeCharacterStorage';

export type UserActivityType =
  | 'search'
  | 'view_creature'
  | 'view_boss'
  | 'view_item'
  | 'view_quest'
  | 'view_zone'
  | 'hunt_search';

export interface UserActivityEntry {
  id: number;
  character_id?: number | null;
  activity_type: UserActivityType | string;
  entity_type?: string | null;
  entity_id?: string | null;
  query?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

interface ActivityCreatePayload {
  activity_type: UserActivityType | string;
  character_id?: number;
  entity_type?: string;
  entity_id?: string;
  query?: string;
  metadata?: Record<string, any>;
}

function scopedCharacterId(explicit?: number | null): number | undefined {
  const value = explicit ?? getActiveCharacterId();
  return value == null ? undefined : value;
}

export const activityApi = {
  async getMine(limit: number = 40, signal?: AbortSignal, characterId?: number | null): Promise<UserActivityEntry[]> {
    const scoped = scopedCharacterId(characterId);
    const response = await api.get('/me/activity', {
      params: { limit, ...(scoped ? { character_id: scoped } : {}) },
      signal,
    });
    return response.data;
  },

  async clearMine(characterId?: number | null): Promise<{ status: string; deleted: number }> {
    const scoped = scopedCharacterId(characterId);
    const response = await api.delete('/me/activity', {
      params: scoped ? { character_id: scoped } : undefined,
    });
    return response.data;
  },

  async record(payload: ActivityCreatePayload): Promise<UserActivityEntry> {
    const characterId = scopedCharacterId(payload.character_id);
    const response = await api.post('/me/activity', {
      ...payload,
      ...(characterId ? { character_id: characterId } : {}),
    });
    return response.data;
  },
};
