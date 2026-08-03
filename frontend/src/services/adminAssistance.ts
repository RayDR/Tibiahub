import api from './api';

export interface AssistedRaffle {
  id: number;
  public_code: string;
  title: string;
  guild_name: string;
  purpose: string;
  status: string;
  execution_state: string;
  timezone_name: string;
  scheduled_run_at_utc: string | null;
  scheduled_run_at_local: string | null;
  participant_count: number;
  version: number;
  safe_to_reschedule: boolean;
  unsafe_reason: string | null;
  eligibility_snapshot: { exists: boolean; valid: boolean; warning: string | null; id: number | null };
  scheduler: { job_id: string | null; claimed_at: string | null; lease_expires_at: string | null; next_retry_at: string | null; retry_count: number; attempt_count: number; last_error_code: string | null };
}

export const adminAssistanceApi = {
  lookupRaffle: async (identifier: string): Promise<AssistedRaffle> =>
    (await api.get('/admin/assistance/raffles/lookup', { params: { identifier } })).data,
  rescheduleRaffle: async (publicCode: string, payload: {
    local_scheduled_at: string;
    timezone_name: string;
    expected_version: number;
    reason: string;
    explicit_confirmation: boolean;
    snapshot_decision: 'preserve' | 'invalidate';
  }): Promise<{ audit_id: number; raffle: AssistedRaffle }> =>
    (await api.patch(`/admin/assistance/raffles/by-code/${encodeURIComponent(publicCode)}/schedule`, payload)).data,
};
