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

export interface KnowledgeRelationshipReview {
  id: string; source_entity_id: string; source_name: string; source_type: string;
  source_scope: string; relationship_type: string; target_type: string; target_name: string | null;
  unresolved_name: string | null; resolution_state: 'unresolved' | 'ambiguous' | 'resolved';
  confidence: string; provider_id: string | null; document_id: string | null;
  candidates: Array<{ id: string; name: string; type: string; slug: string }>;
  created_at: string;
}

export interface KnowledgeRelationshipProvenance {
  relationship_id: string; provider_id: string | null; document_id: string | null;
  job_id: string | null; confidence: string; manual_override: boolean;
  verified_at: string | null; valid_from: string; valid_until: string | null;
  is_current: boolean; superseded_by_id: string | null; safe_context: Record<string, unknown>;
}

export const knowledgeOperationsApi = {
  providers: async (signal?: AbortSignal) => (await api.get<KnowledgeProvider[]>('/admin/knowledge/providers', { signal })).data,
  bootstrapTibiaWiki: async (confirmation: string, batch_limit = 50) => (
    await api.post<{ provider_id: string; enabled: boolean; job_ids: string[]; jobs_created: number }>('/admin/knowledge/bootstrap/tibiawiki', { confirmation, batch_limit })
  ).data,
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
  relationshipReview: async (params: { resolution_state: 'resolved' | 'unresolved' | 'ambiguous'; skip?: number; limit?: number }, signal?: AbortSignal) => (
    await api.get<{ items: KnowledgeRelationshipReview[]; total: number; skip: number; limit: number }>('/admin/knowledge/relationships/review', { params, signal })
  ).data,
  relationshipProvenance: async (id: string) => (await api.get<KnowledgeRelationshipProvenance>(`/admin/knowledge/relationships/${encodeURIComponent(id)}/provenance`)).data,
  resolveRelationship: async (id: string, target_entity_id: string, reason: string) => (await api.post<KnowledgeRelationshipReview>(`/admin/knowledge/relationships/${encodeURIComponent(id)}/resolve`, { target_entity_id, reason })).data,
  rejectRelationship: async (id: string, reason: string) => api.post(`/admin/knowledge/relationships/${encodeURIComponent(id)}/reject`, { reason }),
  verifyRelationship: async (id: string, reason: string) => (await api.post<KnowledgeRelationshipReview>(`/admin/knowledge/relationships/${encodeURIComponent(id)}/verify`, { reason })).data,
};
