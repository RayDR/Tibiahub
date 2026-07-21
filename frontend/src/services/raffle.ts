import api from './api';

export type RaffleAccessMode = 'guild_only' | 'world_only' | 'public';
export type RaffleStatus = 'draft' | 'open' | 'closed' | 'completed' | 'cancelled' | 'deleted';

export interface RafflePrizeInput {
  name: string;
  reward: string;
  order_index?: number;
}

export interface RaffleParticipant {
  id: number;
  user_id: number;
  username: string;
  character_name: string;
  guild_rank?: string;
  weight: number;
  weight_multiplier: number;
  is_eligible: boolean;
  created_at: string;
}

export interface RafflePrize {
  id: number;
  name: string;
  reward: string;
  order_index: number;
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
  async list(): Promise<Raffle[]> {
    const response = await api.get('/raffles/');
    return response.data;
  },

  async get(raffleId: number): Promise<Raffle> {
    const response = await api.get(`/raffles/${raffleId}`);
    return response.data;
  },

  async update(raffleId: number, payload: Partial<{ title: string; description: string; guild_name: string; access_mode: RaffleAccessMode; show_participants: boolean; visibility: string; registration_enabled: boolean; run_mode: string; scheduled_run_at: string; archive_after_days: number; status: RaffleStatus }>): Promise<Raffle> {
    const response = await api.put(`/raffles/${raffleId}`, payload);
    return response.data;
  },

  async share(raffleId: number): Promise<{ public_code: string; url: string }> {
    const response = await api.get(`/raffles/${raffleId}/share`);
    return response.data;
  },

  async create(payload: { title: string; description?: string; guild_name: string; access_mode?: RaffleAccessMode; show_participants?: boolean; prizes: RafflePrizeInput[] }): Promise<Raffle> {
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

  async updateWeightMultiplier(raffleId: number, participantId: number, weightMultiplier: number): Promise<Raffle> {
    const response = await api.patch(`/raffles/${raffleId}/participants/${participantId}/weight`, { weight_multiplier: weightMultiplier });
    return response.data;
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
};
