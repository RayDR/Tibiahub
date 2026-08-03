import api, { ADMIN_ACTION_TIMEOUT_MS } from './api';

export type GuildCapability = 'raffles.manage' | 'events.manage' | 'hunts.manage' | 'announcements.manage';

export interface CharacterIdentity {
  id: number; character_name: string; world_name?: string; guild_name?: string; guild_rank?: string;
  level?: number; vocation?: string; residence?: string; achievement_points?: number;
  ownership_status: string; verification_method?: string; ownership_verified_at?: string;
  is_primary: boolean; is_current_roster_member: boolean; guild_capabilities: Record<GuildCapability, boolean>;
}

export interface GuildIdentity {
  guild_name: string; world_name?: string; role: string; representative_character_name?: string;
  capabilities: Record<GuildCapability, boolean>; can_grant_permissions: boolean;
}

export interface ProfileIdentity {
  id: number; username: string; display_name?: string; title?: string; email?: string; email_verified_at?: string;
  avatar_url?: string; tibia_character_name?: string; guild_name?: string; guild_rank?: string; world_name?: string;
  residence?: string; vocation?: string; level?: number; achievement_points?: number; is_active: boolean;
  is_superuser: boolean; created_at: string; join_date?: string; primary_character_id?: number;
  character_details: CharacterIdentity[]; guild_contexts: GuildIdentity[];
  in_app_notifications_enabled: boolean; email_notifications_enabled: boolean;
}

export interface OwnershipClaim {
  id: number; character_name: string; status: string; expires_at: string; created_at: string;
  verification_requested_at?: string; verified_at?: string; safe_failure_code?: string; challenge?: string; incoming?: boolean;
}

export interface PublicProfile {
  username: string; display_name?: string; title?: string; avatar_url?: string;
  primary_character?: CharacterIdentity; characters: CharacterIdentity[];
  guilds: Array<{ guild_name: string; world_name?: string; guild_rank?: string; character_name: string }>;
}

export const profileApi = {
  me: async (): Promise<ProfileIdentity> => (await api.get('/profile/me')).data,
  update: async (payload: Record<string, string>): Promise<ProfileIdentity> => (await api.put('/profile/me', payload)).data,
  uploadAvatar: async (file: File): Promise<ProfileIdentity> => {
    const form = new FormData(); form.append('image', file);
    return (await api.post('/profile/me/avatar', form, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: ADMIN_ACTION_TIMEOUT_MS })).data;
  },
  removeAvatar: async (): Promise<ProfileIdentity> => (await api.delete('/profile/me/avatar')).data,
  setPrimary: async (characterId: number): Promise<ProfileIdentity> => (await api.post('/profile/me/primary-character', { character_id: characterId })).data,
  refreshCharacter: async (characterId: number): Promise<CharacterIdentity> => (await api.post(`/profile/me/characters/${characterId}/refresh`, undefined, { timeout: ADMIN_ACTION_TIMEOUT_MS })).data,
  unlinkCharacter: async (character: CharacterIdentity, reason: string): Promise<ProfileIdentity> => (await api.delete(`/profile/me/characters/${character.id}`, { data: { confirmation: character.character_name, reason } })).data,
  preferences: async (inApp: boolean, email: boolean): Promise<ProfileIdentity> => (await api.put('/profile/me/notification-preferences', { in_app_notifications_enabled: inApp, email_notifications_enabled: email })).data,
  claims: async (): Promise<OwnershipClaim[]> => (await api.get('/character-ownership/claims')).data,
  incomingClaims: async (): Promise<OwnershipClaim[]> => (await api.get('/character-ownership/incoming-transfers')).data,
  claim: async (name: string): Promise<OwnershipClaim> => (await api.post('/character-ownership/claims', { character_name: name })).data,
  getClaim: async (id: number): Promise<OwnershipClaim> => (await api.get(`/character-ownership/claims/${id}`)).data,
  verifyClaim: async (id: number): Promise<OwnershipClaim> => (await api.post(`/character-ownership/claims/${id}/verify`)).data,
  cancelClaim: async (id: number): Promise<OwnershipClaim> => (await api.post(`/character-ownership/claims/${id}/cancel`)).data,
  requestVerification: async (locale: 'en'|'es'): Promise<void> => { await api.post('/email-verification/request', { locale }); },
  public: async (username: string): Promise<PublicProfile> => (await api.get(`/profile/public/${encodeURIComponent(username)}`)).data,
};
