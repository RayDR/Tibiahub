import api from './api';

export type RaffleAccessMode = 'guild_only' | 'world_only' | 'public';
export type RaffleScope = 'guild' | 'server' | 'global';
export type RaffleStatus = 'draft' | 'open' | 'closed' | 'completed' | 'cancelled' | 'deleted';

export interface RafflePrizeInput {
  name: string;
  reward: string;
  order_index?: number;
  position?: 'second' | 'first';
  amount?: number;
  currency?: string;
}

export interface RaffleParticipant {
  id: number;
  user_id?: number;
  guild_roster_character_id?: number;
  username?: string;
  character_name: string;
  normalized_character_name: string;
  account_identity_known: boolean;
  guild_rank?: string;
  weight: number;
  weight_multiplier: number;
  is_eligible: boolean;
  created_at: string;
  source?: string;
  eligibility_override?: boolean | null;
  eligibility_override_reason?: string;
}

export interface RafflePrize {
  id: number;
  name: string;
  reward: string;
  order_index: number;
  position?: 'second' | 'first';
  amount?: number;
  currency?: string;
}

export interface RaffleWinner {
  id: number;
  prize_id: number;
  prize_name: string;
  reward: string;
  participant_id: number;
  user_id: number;
  username: string;
  character_name: string;
  run_number: number;
  is_rerun: boolean;
  rerun_reason?: string;
  created_at: string;
}

export interface Raffle {
  id: number;
  public_code: string;
  title: string;
  description?: string;
  guild_name: string;
  scope_type: RaffleScope;
  world_name?: string;
  access_mode: RaffleAccessMode;
  show_participants: boolean;
  participant_count: number;
  visibility: 'public' | 'private';
  registration_enabled: boolean;
  run_mode: 'manual' | 'automatic';
  scheduled_run_at?: string;
  archive_after_days: number;
  archived_at?: string;
  status: RaffleStatus;
  current_run_number: number;
  rerun_count: number;
  created_at: string;
  updated_at: string;
  participants: RaffleParticipant[];
  prizes: RafflePrize[];
  current_winners: RaffleWinner[];
  history: RaffleWinner[];
  purpose: 'test' | 'real' | 'legacy';
  timezone_name: string;
  eligibility_days: number;
  publication_status: 'private' | 'published';
  execution_state: 'pending' | 'claimed' | 'running' | 'failed' | 'succeeded';
  executed_at?: string;
  scheduler_job_id?: string;
  claimed_at?: string;
  lease_expires_at?: string;
  last_error_code?: string;
  last_error_summary?: string;
  retry_count: number;
  next_retry_at?: string;
  unique_account_participation: boolean;
  weighting_mode: 'equal' | 'weighted';
}

export interface RaffleCandidate {
  roster_character_id: number; character_name: string; rank?: string; level?: number;
  vocation?: string; last_activity_at: string; linked_user_id?: number; linked_username?: string;
  account_identity_key?: string; account_identity_known: boolean; already_participating: boolean;
  selectable: boolean; reason?: string;
}

export interface EligibilityPreview {
  raffle_id: number; cutoff_at: string; timezone_name: string; eligibility_days: number;
  candidate_count: number; eligible_count: number; excluded_count: number; snapshot_hash: string;
  persisted: boolean; snapshot_id?: number;
  entries: Array<{ character_name?: string; guild_name?: string; guild_rank?: string; last_activity_at?: string; is_eligible: boolean; exclusion_code?: string; exclusion_summary?: string }>;
}

export interface AutomaticResult {
  id: number; prize_id: number; prize_position: 'second' | 'first'; prize_name: string;
  amount: number; currency: string; character_name: string; selection_index: number;
  candidate_count: number; delivery_status: 'pending' | 'delivered' | 'disputed' | 'cancelled'; delivery_deadline_at: string;
  delivered_at?: string; delivered_by_name?: string; delivery_note?: string;
  delivery_history?: Array<{ previous_status: string; new_status: string; actor: string; note?: string; admin_override: boolean; created_at: string }>;
}

export interface AutomaticRun {
  id: number; raffle_id: number; run_number: number; snapshot_id: number; parent_run_id?: number;
  trigger: string; state: string; started_at?: string; completed_at?: string; failure_code?: string;
  failure_summary?: string; algorithm_version: string; entropy_commitment?: string; results: AutomaticResult[];
}

export interface RaffleWorkspaceItem {
  id: number; public_code: string; title: string; guild_name: string; scope_type: RaffleScope; world_name?: string;
  purpose: 'test' | 'real' | 'legacy'; status: RaffleStatus; scheduled_run_at?: string;
  publication_status: 'private' | 'published'; execution_state: Raffle['execution_state']; participant_count: number;
  last_error_summary?: string; retry_count: number;
  eligibility?: { candidate_count: number; eligible_count: number; excluded_count: number; cutoff_at: string; frozen: boolean };
  winners: Array<{ prize_position: 'second' | 'first'; prize_name: string; amount: number; currency: string; character_name: string; delivery_status: AutomaticResult['delivery_status']; delivery_deadline_at: string }>;
  capabilities: { manage: boolean; publish: boolean };
  actions?: {
    view_detail: { enabled: boolean; reason?: string | null };
    edit: { enabled: boolean; reason?: string | null };
    edit_prizes: { enabled: boolean; reason?: string | null };
    cancel_archive: { enabled: boolean; reason?: string | null };
    permanent_delete: { enabled: boolean; reason?: string | null };
  };
}

export interface RaffleExecution {
  raffle_id: number;
  run_number: number;
  winner_count: number;
  winners: RaffleWinner[];
}

export interface RaffleSimulation {
  raffle_id: number;
  run_number: number;
  winner_count: number;
  winners: RaffleWinner[];
  simulation: true;
  status: RaffleStatus;
  access_mode: RaffleAccessMode;
  eligible_count: number;
  ineligible_count: number;
  participant_count: number;
  prizes: Array<{ id: number; name: string; reward: string; order_index: number }>;
  eligible_participants: Array<{
    participant_id: number;
    user_id: number;
    username: string;
    character_name: string;
    guild_rank?: string;
    weight: number;
    weight_multiplier: number;
  }>;
  ineligible_participants: Array<{ participant_id: number; user_id?: number; character_name: string; guild_rank?: string; weight: number; weight_multiplier: number; reason: string }>;
  warnings: string[];
}

export interface PublicRaffle {
  public_code: string;
  title: string;
  description?: string;
  guild_name: string;
  access_mode: RaffleAccessMode;
  purpose: 'test' | 'real' | 'legacy';
  timezone_name: string;
  scheduled_run_at?: string;
  status: RaffleStatus;
  publication_status: 'private' | 'reviewed' | 'published';
  show_participants: boolean;
  participant_count: number;
  participants: Array<{ character_name: string; guild_rank?: string }>;
  prizes: RafflePrize[];
  winners: Array<{
    prize_position: 'second' | 'first';
    prize_name: string;
    amount: number;
    currency: string;
    character_name: string;
    delivery_status: 'pending' | 'delivered' | 'disputed' | 'cancelled';
    delivery_deadline_at: string;
  }>;
}

export const raffleApi = {
  async workspace(): Promise<RaffleWorkspaceItem[]> { return (await api.get('/raffles/workspace')).data; },
  async list(): Promise<Raffle[]> {
    const response = await api.get('/raffles/');
    return response.data;
  },

  async get(raffleId: number): Promise<Raffle> {
    const response = await api.get(`/raffles/${raffleId}`);
    return response.data;
  },

  async update(raffleId: number, payload: Partial<{ title: string; description: string; guild_name: string; access_mode: RaffleAccessMode; show_participants: boolean; visibility: string; registration_enabled: boolean; run_mode: string; scheduled_run_at: string; timezone_name: string; eligibility_days: number; archive_after_days: number; status: RaffleStatus; unique_account_participation: boolean; weighting_mode: 'equal' | 'weighted' }>): Promise<Raffle> {
    const response = await api.put(`/raffles/${raffleId}`, payload);
    return response.data;
  },

  async share(raffleId: number): Promise<{ public_code: string; url: string }> {
    const response = await api.get(`/raffles/${raffleId}/share`);
    return response.data;
  },

  async create(payload: { title: string; description?: string; guild_name: string; scope_type?: RaffleScope; world_name?: string; access_mode?: RaffleAccessMode; show_participants?: boolean; prizes: RafflePrizeInput[]; purpose?: 'test' | 'real' | 'legacy'; run_mode?: 'manual' | 'automatic'; scheduled_run_at?: string; timezone_name?: string; eligibility_days?: number; unique_account_participation?: boolean; weighting_mode?: 'equal' | 'weighted' }): Promise<Raffle> {
    const response = await api.post('/raffles/', payload);
    return response.data;
  },

  async addPrize(raffleId: number, payload: RafflePrizeInput): Promise<Raffle> {
    const response = await api.post(`/raffles/${raffleId}/prizes`, payload);
    return response.data;
  },

  async syncParticipants(raffleId: number): Promise<Raffle> {
    const response = await api.post(`/raffles/${raffleId}/participants/sync`);
    return response.data;
  },

  async addManualParticipant(raffleId: number, characterName: string): Promise<Raffle> {
    const response = await api.post(`/raffles/${raffleId}/participants/manual`, { character_name: characterName });
    return response.data;
  },

  async updateWeight(raffleId: number, participantId: number, weight: number): Promise<Raffle> {
    const response = await api.patch(`/raffles/${raffleId}/participants/${participantId}/weight`, { weight });
    return response.data;
  },

  async candidates(raffleId: number, days: 7 | 15 | 30, search?: string): Promise<RaffleCandidate[]> {
    return (await api.get(`/raffles/${raffleId}/participant-candidates`, { params: { days, search } })).data;
  },
  async refreshGuildRoster(raffleId: number): Promise<Record<string, number | string>> {
    return (await api.post(`/raffles/${raffleId}/guild-roster/sync`)).data;
  },
  async addRosterParticipants(raffleId: number, rosterCharacterIds: number[], replaceExisting = false, addAllEligible = false, activityDays: 7 | 15 | 30 = 30): Promise<{ added: number; restored: number; removed: number; unchanged: number }> {
    return (await api.post(`/raffles/${raffleId}/participants/bulk`, { roster_character_ids: rosterCharacterIds, replace_existing: replaceExisting, add_all_eligible: addAllEligible, activity_days: activityDays })).data;
  },
  async removeParticipants(raffleId: number, participantIds: number[], reason?: string): Promise<{ removed: number }> {
    return (await api.post(`/raffles/${raffleId}/participants/remove`, { participant_ids: participantIds, reason })).data;
  },
  async updateParticipationSettings(raffleId: number, payload: { unique_account_participation?: boolean; weighting_mode?: 'equal' | 'weighted' }): Promise<Raffle> {
    return (await api.patch(`/raffles/${raffleId}/participation-settings`, payload)).data;
  },
  async manageableGuildContext(): Promise<{ guilds: string[]; guild_worlds: Record<string, string | null> }> {
    return (await api.get('/guild-management/manageable-guilds', { params: { capability: 'raffles.manage' } })).data;
  },
  async manageableGuilds(): Promise<string[]> {
    return (await api.get('/guild-management/manageable-guilds', { params: { capability: 'raffles.manage' } })).data.guilds;
  },

  async draw(raffleId: number, dryRun: boolean = false): Promise<RaffleExecution> {
    const response = await api.post(`/raffles/${raffleId}/draw`, { dry_run: dryRun });
    return response.data;
  },

  async rerun(raffleId: number, reason: string): Promise<RaffleExecution> {
    const response = await api.post(`/raffles/${raffleId}/rerun`, { reason });
    return response.data;
  },

  async removeParticipant(raffleId: number, participantId: number): Promise<Raffle> {
    const response = await api.delete(`/raffles/${raffleId}/participants/${participantId}`);
    return response.data;
  },

  async getPublic(raffleId: number): Promise<PublicRaffle> {
    const response = await api.get(`/raffles/public/${raffleId}`);
    return response.data;
  },

  async getPublicByCode(publicCode: string): Promise<PublicRaffle> {
    const response = await api.get(`/raffles/public/code/${publicCode}`);
    return response.data;
  },

  async registerPublic(raffleId: number, characterName: string): Promise<PublicRaffle> {
    const response = await api.post(`/raffles/public/${raffleId}/register`, { character_name: characterName });
    return response.data;
  },

  async registerPublicByCode(publicCode: string, characterName: string): Promise<PublicRaffle> {
    const response = await api.post(`/raffles/public/code/${publicCode}/register`, { character_name: characterName });
    return response.data;
  },

  async simulate(raffleId: number): Promise<RaffleSimulation> {
    const response = await api.post(`/raffles/${raffleId}/simulate`);
    return response.data;
  },

  async softDelete(raffleId: number, reason?: string): Promise<Raffle> {
    const response = await api.delete(`/raffles/${raffleId}`, { params: { reason } });
    return response.data;
  },

  async permanentDelete(raffleId: number, reason: string, confirmation: string): Promise<{ id: number; deleted: true; audit_preserved: boolean }> {
    const response = await api.delete(`/raffles/${raffleId}/permanent`, { params: { reason, confirmation } });
    return response.data;
  },
  async previewEligibility(raffleId: number): Promise<EligibilityPreview> {
    const response = await api.post(`/raffles/${raffleId}/eligibility/preview`);
    return response.data;
  },
  async freezeEligibility(raffleId: number): Promise<EligibilityPreview> {
    const response = await api.post(`/raffles/${raffleId}/eligibility/freeze`);
    return response.data;
  },
  async runs(raffleId: number): Promise<AutomaticRun[]> {
    const response = await api.get(`/raffles/${raffleId}/runs`);
    return response.data;
  },
  async rerunAutomatic(raffleId: number, positions: Array<'second' | 'first'>, reason: string, overrideDelivered = false, overrideReason?: string): Promise<AutomaticRun> {
    const response = await api.post(`/raffles/${raffleId}/reruns`, { positions, reason, override_delivered: overrideDelivered, override_reason: overrideReason });
    return response.data;
  },
  async publish(raffleId: number): Promise<void> { await api.post(`/raffles/${raffleId}/publish`); },
  async unpublish(raffleId: number): Promise<void> { await api.post(`/raffles/${raffleId}/unpublish`); },
  async updateDelivery(raffleId: number, resultId: number, status: AutomaticResult['delivery_status'], note?: string, adminOverride = false): Promise<void> {
    await api.patch(`/raffles/${raffleId}/results/${resultId}/delivery`, { status, note, admin_override: adminOverride });
  },
  async overrideTestEligibility(raffleId: number, participantId: number, eligible: boolean, reason: string): Promise<void> {
    await api.patch(`/raffles/${raffleId}/participants/${participantId}/test-eligibility-override`, { eligible, reason });
  },
  async retryTest(raffleId: number, reason: string): Promise<void> {
    await api.post(`/raffles/${raffleId}/test-retry`, { reason });
  },
  async cleanupTest(raffleId: number, reason: string): Promise<{ raffle_id: number; archived: boolean; participant_associations_removed: number; users_modified: number; guilds_modified: number; real_raffles_modified: number }> {
    return (await api.post(`/raffles/${raffleId}/test-cleanup`, { confirmation: 'ARCHIVE TEST RAFFLE', reason })).data;
  },
};
