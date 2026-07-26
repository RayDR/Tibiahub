import api from './api';

export type MaintenanceCategory = 'guilds' | 'users' | 'characters' | 'raffles' | 'leadership' | 'events' | 'hunts' | 'knowledge';

export interface MaintenanceItem {
  category: MaintenanceCategory;
  id: string;
  label: string;
  action: string;
  deletable: boolean;
  blockers: string[];
  counts: Record<string, number>;
  confirmation: string;
}

export const maintenanceApi = {
  list: async (category: MaintenanceCategory, search = ''): Promise<MaintenanceItem[]> =>
    (await api.get(`/admin/maintenance/${category}`, { params: { search } })).data.items,
  preflight: async (item: MaintenanceItem): Promise<MaintenanceItem> =>
    (await api.get(`/admin/maintenance/${item.category}/${encodeURIComponent(item.id)}/preflight`)).data,
  execute: async (item: MaintenanceItem, confirmation: string, reason: string): Promise<MaintenanceItem & { executed: boolean }> =>
    (await api.post(`/admin/maintenance/${item.category}/${encodeURIComponent(item.id)}/execute`, { confirmation, reason })).data,
};
