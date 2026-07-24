import api from './api';

export type KnowledgeJobState = 'pending' | 'claimed' | 'running' | 'retrying' | 'succeeded' | 'partially_succeeded' | 'failed' | 'cancelled';

export interface KnowledgeProvider {
  provider_id: string;
  provider_name: string;
  priority: number;
  enabled: boolean;
  version: string | null;
  health: string;
  last_attempted_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  consecutive_failures: number;
  cooldown_until: string | null;
  supports_entities: string[];
  supports_media: boolean;
  supports_search: boolean;
  supported_job_types: string[];
}

export interface KnowledgeWorkerHeartbeat {
  worker_id: string;
  worker_type: string;
  node_id: string;
  process_id: number;
  started_at: string;
  last_seen_at: string;
  current_job_id: string | null;
  state: string;
  version: string;
  safe_metadata: Record<string, unknown>;
}

export interface KnowledgeJobAttempt {
  id: string;
  attempt_number: number;
  worker_id: string;
  started_at: string;
  completed_at: string | null;
  outcome: string;
  retryable: boolean;
  error_code: string | null;
  safe_error: string | null;
  metrics: Record<string, number>;
}

export interface KnowledgeJob {
  id: string;
  provider_id: string;
  job_type: string;
  entity_type: string | null;
  scope: Record<string, unknown>;
  priority: number;
  state: KnowledgeJobState;
  scheduled_at: string;
  claimed_at: string | null;
  lease_expires_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  worker_id: string | null;
  attempt_count: number;
  max_attempts: number;
  parent_job_id: string | null;
  correlation_id: string;
  last_error_code: string | null;
  safe_last_error: string | null;
  trigger: string;
  created_at: string;
  updated_at: string;
  can_retry: boolean;
  can_cancel: boolean;
}

export interface KnowledgeJobDetail extends KnowledgeJob {
  attempts: KnowledgeJobAttempt[];
}

export const knowledgeOperationsApi = {
  providers: async (signal?: AbortSignal) => (await api.get<KnowledgeProvider[]>('/admin/knowledge/providers', { signal })).data,
  workers: async (signal?: AbortSignal) => (await api.get<KnowledgeWorkerHeartbeat[]>('/admin/knowledge/workers', { signal })).data,
  jobs: async (params: { provider_id?: string; entity_type?: string; state?: string; skip?: number; limit?: number }, signal?: AbortSignal) => (
    await api.get<{ items: KnowledgeJob[]; total: number; skip: number; limit: number }>('/admin/knowledge/jobs', { params, signal })
  ).data,
  job: async (jobId: string) => (await api.get<KnowledgeJobDetail>(`/admin/knowledge/jobs/${encodeURIComponent(jobId)}`)).data,
  enqueue: async (payload: {
    provider_id: string;
    job_type: string;
    entity_type: string;
    scope: Record<string, unknown>;
    payload: Record<string, unknown>;
    confirm_catalog_sync?: boolean;
    allow_completed_recreate?: boolean;
  }) => (await api.post<{ item: KnowledgeJob; created: boolean }>('/admin/knowledge/jobs', payload)).data,
  retry: async (jobId: string) => (await api.post<KnowledgeJob>(`/admin/knowledge/jobs/${encodeURIComponent(jobId)}/retry`)).data,
  cancel: async (jobId: string) => (await api.post<KnowledgeJob>(`/admin/knowledge/jobs/${encodeURIComponent(jobId)}/cancel`)).data,
};
