import api from './api';

export interface InternalNotification {
  id: number; guild_name?: string; raffle_id?: number; notification_type: string;
  title_key: string; message_key: string; interpolation: Record<string, unknown>;
  deep_link?: string; is_read: boolean; created_at: string; read_at?: string;
}

export const notificationApi = {
  async list(): Promise<InternalNotification[]> { return (await api.get('/notifications')).data; },
  async unreadCount(): Promise<number> { return (await api.get('/notifications/unread-count')).data.unread_count; },
  async markRead(id: number): Promise<void> { await api.post(`/notifications/${id}/read`); },
  async markAllRead(): Promise<void> { await api.post('/notifications/read-all'); },
};
