import api from './api';

export interface MaintenanceHold {
  id: number;
  hold_type: 'manual' | 'sync';
  owner_job_id: string | null;
  reason: string;
  public_message: string;
  enabled_at: string;
  planned_end_at: string | null;
  auto_release: boolean;
  released_at: string | null;
  release_reason: string | null;
  last_heartbeat_at: string | null;
  safe_metadata: Record<string, unknown>;
}

export interface MaintenanceStatus {
  active: boolean;
  message: string | null;
  started_at: string | null;
  planned_end_at: string | null;
  service_status: 'online' | 'maintenance';
  holds?: MaintenanceHold[];
}

export const maintenanceModeApi = {
  status: async (signal?: AbortSignal): Promise<MaintenanceStatus> =>
    (await api.get('/maintenance/status', { signal })).data,
  adminStatus: async (): Promise<MaintenanceStatus> =>
    (await api.get('/admin/maintenance')).data,
  enableManual: async (payload: { reason: string; public_message: string; planned_end_at: string | null; confirmation: string }): Promise<MaintenanceStatus> =>
    (await api.post('/admin/maintenance/manual/enable', payload)).data,
  disableManual: async (reason: string): Promise<MaintenanceStatus> =>
    (await api.post('/admin/maintenance/manual/disable', { reason, confirmation: 'DISABLE MAINTENANCE' })).data,
  release: async (id: number, reason: string): Promise<MaintenanceHold> =>
    (await api.post(`/admin/maintenance/holds/${id}/release`, { reason })).data,
};
