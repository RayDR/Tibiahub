import api from './api';

export interface SyncPhase {
  id: number;
  phase_key: string;
  order_index: number;
  provider: string | null;
  required: boolean;
  status: string;
  attempt_count: number;
  max_attempts: number;
  processed_count: number;
  failed_count: number;
  current_entity: string | null;
  current_offset: number;
  checkpoint: Record<string, unknown>;
  next_retry_at: string | null;
  started_at: string | null;
  updated_at: string;
  finished_at: string | null;
  error_category: string | null;
  safe_error: string | null;
}

export interface SyncJob {
  job_id: string;
  job_type: string;
  status: string;
  operation_status: string;
  progress_percent: number;
  message: string | null;
  cancel_requested: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  summary: Record<string, unknown> | null;
  operation_label: string | null;
  worker_id: string | null;
  lease_expires_at: string | null;
  maintenance_requested: boolean;
  maintenance_active: boolean;
  continue_on_error: boolean;
  phases: SyncPhase[];
}

export interface FullSyncOptions {
  maintenance_enabled: boolean;
  continue_on_error: boolean;
  include_images: boolean;
  include_knowledge: boolean;
  include_guild_rosters: boolean;
  force_refresh: boolean;
  batch_size: number;
  max_retries: number;
  external_timeout_seconds: number;
  operation_label: string;
  confirmation: string;
}

export const fullSyncApi = {
  jobs: async (): Promise<SyncJob[]> => (await api.get('/admin/sync/jobs', { params: { limit: 30 } })).data,
  start: async (options: FullSyncOptions): Promise<{ job_id: string }> => (await api.post('/admin/sync/full', options)).data,
  cancel: async (id: string): Promise<SyncJob> => (await api.post(`/admin/sync/jobs/${id}/cancel`)).data,
  resume: async (id: string): Promise<SyncJob> => (await api.post(`/admin/sync/jobs/${id}/resume`)).data,
  resumePhase: async (id: string, phase: string): Promise<SyncJob> => (await api.post(`/admin/sync/jobs/${id}/phases/${encodeURIComponent(phase)}/resume`)).data,
  skipPhase: async (id: string, phase: string, reason: string): Promise<SyncJob> => (await api.post(`/admin/sync/jobs/${id}/phases/${encodeURIComponent(phase)}/skip`, undefined, { params: { reason } })).data,
};
