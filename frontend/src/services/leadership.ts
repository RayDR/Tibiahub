import api from './api';

export type ApplicationStatus = 'applied' | 'under_review' | 'more_information_requested' | 'interview' | 'voting' | 'accepted' | 'rejected' | 'withdrawn' | 'cancelled';
export interface LeadershipSummary { guild_name: string; active_viceleaders: number; recommended_minimum: number; target_count: number; below_recommended: boolean; open_positions: number; active_applicants?: number; applications_requiring_attention?: number; interviews_pending: number; applications_voting: number; recently_accepted: number; pending_promotions?: number; own_status?: ApplicationStatus; own_application_id?: number; capabilities: { manage: boolean; review: boolean } }
export interface LeadershipOpening { id: number; role_code: string; title: string; description?: string; responsibilities: string; requirements: string; openings_count: number; filled_count: number; application_deadline?: string; status: 'draft' | 'open' | 'paused' | 'closed' | 'archived'; allow_viceleader_review: boolean; voting_enabled: boolean; votes_required: number; created_at: string; updated_at: string }
export type LeadershipAction = 'withdraw'|'reply'|'comment'|'vote'|'start_review'|'request_information'|'schedule_interview'|'start_voting'|'accept'|'reject'|'cancel'|'return_to_review';
export interface LeadershipAssignment { id:number; role_code:string; character_name:string; assignment_source:string; started_at:string; ended_at?:string; is_active:boolean; notes?:string; assigned_by?:string; in_game_promotion_status:'pending'|'completed'; in_game_promoted_at?:string; in_game_promoted_by?:string }
export interface LeadershipApplication { id: number; opening_id: number; opening_title:string; role_code:string; character_name: string; status: ApplicationStatus; profile: Record<string, string | number | null>; submitted_at: string; conduct_agreed_at: string; conduct_version: string; final_decision_at?:string; rejection_reason?:string; valid_actions:LeadershipAction[]; answers?: Record<string, string>; history: Array<{ from_status?: string; to_status: string; reason?: string; actor_name?:string; actor_context?:string; admin_assistance?:boolean; created_at: string }>; messages: Array<{ id: number; audience: string; message_type: string; body: string; author_name: string; created_at: string }>; interview?: { scheduled_at: string; timezone: string; meeting_location: string; completed_at?: string; organizer?:string; completed_by?:string; internal_notes?:string }; vote_summary?: { support: number; neutral: number; oppose: number }; vote_participation?: number; current_vote?:'support'|'neutral'|'oppose'; current_vote_comment?:string; assignment?:LeadershipAssignment }

function paths(guildKey?: string) { const root = guildKey ? `/admin/guilds/${encodeURIComponent(guildKey)}/leadership` : '/guild/me/leadership'; return {
  summary: root, openings: `${root}/openings`, applications: `${root}/applications`,
}; }

export const leadershipApi = {
  summary: async (guildKey?: string): Promise<LeadershipSummary> => (await api.get(paths(guildKey).summary)).data,
  openings: async (guildKey?: string): Promise<LeadershipOpening[]> => (await api.get(paths(guildKey).openings)).data,
  createOpening: async (payload: Record<string, unknown>, guildKey?: string): Promise<LeadershipOpening> => (await api.post(paths(guildKey).openings, payload)).data,
  openingAction: async (id: number, action: 'open' | 'pause' | 'close' | 'archive', guildKey?: string): Promise<LeadershipOpening> => (await api.post(`${paths(guildKey).openings}/${id}/${action}`)).data,
  applications: async (guildKey?: string): Promise<LeadershipApplication[]> => (await api.get(paths(guildKey).applications)).data,
  mine: async (): Promise<LeadershipApplication[]> => (await api.get('/guild/me/leadership/applications/mine')).data,
  application: async (id: number, guildKey?: string): Promise<LeadershipApplication> => (await api.get(`${paths(guildKey).applications}/${id}`)).data,
  apply: async (openingId: number, payload: Record<string, unknown>): Promise<LeadershipApplication> => (await api.post(`/guild/me/leadership/openings/${openingId}/applications`, payload)).data,
  status: async (id: number, status: ApplicationStatus, reason?: string, guildKey?: string): Promise<LeadershipApplication> => (await api.patch(`${paths(guildKey).applications}/${id}/status`, { status, reason })).data,
  withdraw: async (id: number): Promise<LeadershipApplication> => (await api.post(`/guild/me/leadership/applications/${id}/withdraw`)).data,
  message: async (id: number, payload: { audience: string; message_type: string; body: string }, guildKey?: string) => (await api.post(`${paths(guildKey).applications}/${id}/messages`, payload)).data,
  interview: async (id: number, payload: Record<string, unknown>, guildKey?: string) => (await api.post(`${paths(guildKey).applications}/${id}/interview`, payload)).data,
  vote: async (id: number, vote: 'support' | 'neutral' | 'oppose', comment?: string, guildKey?: string) => (await api.post(`${paths(guildKey).applications}/${id}/votes`, { vote, comment })).data,
  decision: async (id: number, decision: 'accepted' | 'rejected', reason?: string, guildKey?: string) => (await api.post(`${paths(guildKey).applications}/${id}/decision`, { decision, reason })).data,
  assignments: async (guildKey?:string):Promise<LeadershipAssignment[]> => (await api.get(`${paths(guildKey).summary}/assignments`)).data,
  promotion: async (id:number, completed:boolean, note?:string, guildKey?:string):Promise<LeadershipAssignment> => (await api.patch(`${paths(guildKey).summary}/assignments/${id}/promotion`, {completed,note})).data,
  endAssignment: async (id:number, reason:string, guildKey?:string):Promise<LeadershipAssignment> => (await api.post(`${paths(guildKey).summary}/assignments/${id}/end`, {reason})).data,
};
