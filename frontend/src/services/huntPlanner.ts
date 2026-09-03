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

export interface GuildHuntZoneSummary {
  canonical_id: string;
  domain_id?: number;
  name: string;
  slug?: string;
  city?: string;
  region?: string;
  min_level?: number;
  max_level?: number;
  recommended_level?: number;
  recommended_vocations?: string[];
  difficulty?: string;
  creature_count: number;
  boss_count: number;
  creature_preview: Array<{
    id?: number;
    canonical_id?: string;
    name: string;
    slug?: string;
    is_boss?: boolean;
    image_url?: string;
  }>;
  access_required?: boolean | null;
  access_quest_count: number;
  access_quests: Array<{ id?: number; canonical_id?: string; name: string; slug?: string }>;
  spatial_state: 'resolved_point' | 'resolved_bounds' | 'knowledge_only' | 'unresolved';
  map_available: boolean;
  map_floor?: number;
  media_url?: string;
  is_current: boolean;
}

export interface GuildHunt {
  id: number;
  guild_name: string;
  scheduled_at: string;
  timezone_name: string;
  server_name: string;
  location: string;
  target: string;
  hunting_zone_id?: string | null;
  hunting_zone_summary?: GuildHuntZoneSummary | null;
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
  hunting_zone_id?: string | null;
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
