import api from './api';

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
  title: string;
  description?: string;
  guild_name: string;
  status: string;
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

export const raffleApi = {
  async list(): Promise<Raffle[]> {
    const response = await api.get('/raffles/');
    return response.data;
  },

  async get(raffleId: number): Promise<Raffle> {
    const response = await api.get(`/raffles/${raffleId}`);
    return response.data;
  },

  async create(payload: { title: string; description?: string; guild_name: string; prizes: RafflePrizeInput[] }): Promise<Raffle> {
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

  async draw(raffleId: number): Promise<RaffleExecution> {
    const response = await api.post(`/raffles/${raffleId}/draw`);
    return response.data;
  },

  async rerun(raffleId: number, reason: string): Promise<RaffleExecution> {
    const response = await api.post(`/raffles/${raffleId}/rerun`, { reason });
    return response.data;
  },
};
