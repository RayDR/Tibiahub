import api from './api';

export type LocalizationStatus = 'generated' | 'reviewed' | 'approved' | 'stale' | 'failed';
export type LocalizationJobStatus = 'pending' | 'processing' | 'retry' | 'succeeded' | 'failed' | 'cancelled';

export interface KnowledgeLocalization {
  id: string;
  entity_uuid: string | null;
  resource_type: string;
  resource_key: string;
  field_path: string;
  language: string;
  text: string;
  source_language: string;
  source_text: string | null;
  source_text_hash: string;
  origin: 'provider' | 'machine' | 'human';
  status: LocalizationStatus;
  provider: string | null;
  provider_model: string | null;
  locked: boolean;
  reviewed_by_id: number | null;
  reviewed_at: string | null;
  approved_by_id: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LocalizationJob {
  id: number;
  entity_uuid: string | null;
  resource_type: string;
  resource_key: string;
  field_path: string;
  source_language: string;
  target_language: string;
  source_text_hash: string;
  status: LocalizationJobStatus;
  attempt_count: number;
  next_attempt_at: string | null;
  safe_failure_category: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface LocalizationDiagnostics {
  enabled: boolean;
  auto_enqueue: boolean;
  provider: string;
  model: string;
  default_language: string;
  target_languages: string[];
  queue_depth: number;
  failed_jobs: number;
  generated_pending_review: number;
  stale: number;
  approved: number;
  worker: null | {
    worker_id: string;
    state: string;
    last_seen_at: string;
    last_success_at: string | null;
    last_failure_category: string | null;
    enabled: boolean;
  };
}

export interface LocalizationBackfillResult {
  resource_type: string;
  scanned: number;
  queued: number;
  next_cursor: number | null;
  exhausted: boolean;
}

export const localizationAdminApi = {
  diagnostics: async (signal?: AbortSignal) => (
    await api.get<LocalizationDiagnostics>('/admin/knowledge/localization-diagnostics', { signal })
  ).data,
  localizations: async (
    params: { status?: LocalizationStatus; language?: string; resource_type?: string; skip?: number; limit?: number },
    signal?: AbortSignal,
  ) => (
    await api.get<{ items: KnowledgeLocalization[]; total: number; skip: number; limit: number }>(
      '/admin/knowledge/localizations',
      { params, signal },
    )
  ).data,
  review: async (id: string, payload: { text?: string; lock?: boolean }) => (
    await api.post<KnowledgeLocalization>(`/admin/knowledge/localizations/${encodeURIComponent(id)}/review`, payload)
  ).data,
  approve: async (id: string, payload: { text?: string }) => (
    await api.post<KnowledgeLocalization>(`/admin/knowledge/localizations/${encodeURIComponent(id)}/approve`, payload)
  ).data,
  unlock: async (id: string) => (
    await api.post<KnowledgeLocalization>(`/admin/knowledge/localizations/${encodeURIComponent(id)}/unlock`)
  ).data,
  enqueueJob: async (payload: {
    entity_uuid?: string | null;
    resource_type: string;
    resource_key: string;
    field_path: string;
    source_text: string;
    source_language: string;
    target_language: string;
    protected_terms?: string[];
    context?: string;
  }) => (
    await api.post<LocalizationJob>('/admin/knowledge/localization-jobs', payload)
  ).data,
  backfill: async (payload: {
    resource_type: 'creature' | 'item' | 'quest' | 'npc' | 'location' | 'hunt_zone';
    after_id?: number;
    limit?: number;
    source_language?: string;
    target_languages?: string[];
  }) => (
    await api.post<LocalizationBackfillResult>('/admin/knowledge/localization-backfill', payload)
  ).data,
};
