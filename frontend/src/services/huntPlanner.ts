import api from './api';

export type HuntView = 'upcoming' | 'week' | 'month';
export type HuntStatus = 'scheduled' | 'in_progress' | 'finished' | 'cancelled';
export type AttendanceStatus = 'registered' | 'attended' | 'absent' | 'left';
export type VocationCode = 'EK' | 'ED' | 'RP' | 'MS';

export interface GuildHuntParticipant {
  id: number;
  user_id: number;
  character_name: string;
  vocation?: string;
  attendance_status: AttendanceStatus;
  joined_at: string;
  left_at?: string;
}

export interface GuildHunt {
  id: number;
  guild_name: string;
  scheduled_at: string;
  timezone_name: string;
  server_name: string;
  location: string;
  target: string;
  recommended_level: number;
  recommended_vocations: VocationCode[];
  maximum_participants: number;
  required_ek: number;
  required_ed: number;
  required_rp: number;
  required_ms: number;
  description?: string;
  discord_channel?: string;
  voice_channel?: string;
  status: HuntStatus;
  cancellation_reason?: string;
  started_at?: string;
  finished_at?: string;
  participants: GuildHuntParticipant[];
  registered_count: number;
  current_user_joined: boolean;
  capabilities: { manage: boolean; join: boolean; attendance: boolean };
}

export interface GuildHuntInput {
  guild_name?: string;
  scheduled_at: string;
  timezone_name: string;
  server_name: string;
  location: string;
  target: string;
  recommended_level: number;
  recommended_vocations: VocationCode[];
  maximum_participants: number;
  required_ek: number;
  required_ed: number;
  required_rp: number;
  required_ms: number;
  description?: string;
  discord_channel?: string;
  voice_channel?: string;
}

export const huntPlannerApi = {
  list: async (params?: { guild_name?: string; start?: string; end?: string; status?: HuntStatus[] }): Promise<GuildHunt[]> =>
    (await api.get('/hunts/planner', { params })).data,
  create: async (payload: GuildHuntInput): Promise<GuildHunt> => (await api.post('/hunts/planner', payload)).data,
  update: async (id: number, payload: Partial<GuildHuntInput>): Promise<GuildHunt> => (await api.patch(`/hunts/planner/${id}`, payload)).data,
  join: async (id: number): Promise<GuildHunt> => (await api.post(`/hunts/planner/${id}/join`)).data,
  leave: async (id: number): Promise<GuildHunt> => (await api.post(`/hunts/planner/${id}/leave`)).data,
  cancel: async (id: number, reason: string): Promise<GuildHunt> => (await api.post(`/hunts/planner/${id}/cancel`, { reason })).data,
  start: async (id: number): Promise<GuildHunt> => (await api.post(`/hunts/planner/${id}/start`)).data,
  finish: async (id: number): Promise<GuildHunt> => (await api.post(`/hunts/planner/${id}/finish`)).data,
  attendance: async (huntId: number, participantId: number, attendance_status: 'attended' | 'absent'): Promise<GuildHunt> =>
    (await api.patch(`/hunts/planner/${huntId}/participants/${participantId}`, { attendance_status })).data,
};
