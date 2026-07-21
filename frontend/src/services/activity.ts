import api from './api';

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
  activity_type: UserActivityType | string;
  entity_type?: string | null;
  entity_id?: string | null;
  query?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

interface ActivityCreatePayload {
  activity_type: UserActivityType | string;
  entity_type?: string;
  entity_id?: string;
  query?: string;
  metadata?: Record<string, any>;
}

export const activityApi = {
  async getMine(limit: number = 40): Promise<UserActivityEntry[]> {
    const response = await api.get('/me/activity', { params: { limit } });
    return response.data;
  },

  async clearMine(): Promise<{ status: string; deleted: number }> {
    const response = await api.delete('/me/activity');
    return response.data;
  },

  async record(payload: ActivityCreatePayload): Promise<UserActivityEntry> {
    const response = await api.post('/me/activity', payload);
    return response.data;
  },
};
