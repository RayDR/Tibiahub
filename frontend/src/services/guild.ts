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

export interface Recruitment {
    id: number;
    recruit_name: string;
    status: 'pending' | 'accepted' | 'rejected';
    created_at: string;
    recruiter?: User;
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
    public_profile_url?: string;
    account_identity_known: boolean;
}

export interface GuildMembersPayload {
    guild_name: string;
    source: 'live' | 'snapshot';
    members: GuildMember[];
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

    getEvents: async (skip: number = 0, limit: number = 20, guildName?: string): Promise<Event[]> => {
        const response = await api.get('/guild/events', { params: { skip, limit, guild_name: guildName || undefined } });
        return response.data;
    },

    createEvent: async (data: any, guildName?: string): Promise<Event> => {
        const response = await api.post('/guild/events', data, { params: { guild_name: guildName || undefined } });
        return response.data;
    },

    attendEvent: async (eventId: number, status: string): Promise<any> => {
        const response = await api.post(`/guild/events/${eventId}/attend`, { status });
        return response.data;
    },

    getRecruitments: async (): Promise<Recruitment[]> => {
        const response = await api.get('/guild/recruitments');
        return response.data;
    },

    reportRecruitment: async (data: { recruit_name: string; notes?: string }): Promise<Recruitment> => {
        const response = await api.post('/guild/recruitments', data);
        return response.data;
    },

    getRaffleParticipants: async (guildName: string, days: number = 10): Promise<any[]> => {
        const response = await api.get('/guild/raffle/participants', { params: { guild_name: guildName, days } });
        return response.data;
    },

    getGuildMembers: async (guildName: string, refresh: boolean = false): Promise<GuildMembersPayload> => {
        const response = await api.get(`/guild/${encodeURIComponent(guildName)}/members`, { params: { refresh } });
        return response.data;
    },

    syncGuildMembers: async (guildName: string): Promise<GuildMembersPayload> => {
        const response = await api.post(`/guild/${encodeURIComponent(guildName)}/members/sync`);
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
