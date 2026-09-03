import api from './api';
import { User } from './auth';

export interface Announcement {
    id: number;
    title: string;
    content: string;
    type: 'general' | 'contest' | 'hunt';
    created_at: string;
    author?: User;
    guild_name?: string;
}

export interface Event {
    id: number;
    title: string;
    description: string;
    start_time: string;
    end_time?: string;
    type: 'quest' | 'hunt' | 'pvp' | 'meeting' | 'other';
    author?: User;
    guild_name?: string;
}

export interface GuildMember {
    character_name: string;
    level?: number;
    vocation?: string;
    rank?: string;
    role?: string;
    last_login?: string;
    world?: string;
    snapshot_at: string;
    linked_user_id?: number;
    linked_username?: string;
    linked_email?: string;
    public_profile_url?: string;
    account_identity_known: boolean;
}

export interface GuildMembersPayload {
    guild_name: string;
    source: 'live' | 'snapshot';
    members: GuildMember[];
    total: number;
    skip: number;
    limit: number;
}

export interface GuildMemberPageParams {
    skip?: number;
    limit?: number;
    search?: string;
    sort?: 'level' | 'name';
}

export interface GuildFeatureFlags {
    guild_raffles_enabled: boolean;
    guild_contests_enabled: boolean;
}

export const guildApi = {
    getAnnouncements: async (skip: number = 0, limit: number = 10, guildName?: string): Promise<Announcement[]> => {
        const response = await api.get('/guild/announcements', { params: { skip, limit, guild_name: guildName || undefined } });
        return response.data;
    },

    createAnnouncement: async (data: { title: string; content: string; type: string }, guildName?: string): Promise<Announcement> => {
        const response = await api.post('/guild/announcements', data, { params: { guild_name: guildName || undefined } });
        return response.data;
    },

    deleteAnnouncement: async (announcementId: number): Promise<Announcement> => {
        const response = await api.delete(`/guild/announcements/${announcementId}`);
        return response.data;
    },

    getEvents: async (skip: number = 0, limit: number = 20, guildName?: string): Promise<Event[]> => {
        const response = await api.get('/guild/events', { params: { skip, limit, guild_name: guildName || undefined } });
        return response.data;
    },

    getRaffleParticipants: async (guildName: string, days: number = 10): Promise<any[]> => {
        const response = await api.get('/guild/raffle/participants', { params: { guild_name: guildName, days } });
        return response.data;
    },

    getGuildMembers: async (guildName: string, params: GuildMemberPageParams = {}, signal?: AbortSignal): Promise<GuildMembersPayload> => {
        const response = await api.get(`/guild/${encodeURIComponent(guildName)}/members`, { params, signal });
        return response.data;
    },

    syncGuildMembers: async (guildName: string, params: GuildMemberPageParams = {}): Promise<GuildMembersPayload> => {
        const response = await api.post(`/guild/${encodeURIComponent(guildName)}/members/sync`, undefined, { params });
        return response.data;
    },

    getFeatureFlags: async (signal?: AbortSignal, timeout: number = 3000): Promise<GuildFeatureFlags> => {
        const response = await api.get('/guild/features', { signal, timeout });
        const payload = response.data || {};
        return {
            guild_raffles_enabled: payload.guild_raffles_enabled !== false,
            guild_contests_enabled: payload.guild_contests_enabled !== false,
        };
    }
};
