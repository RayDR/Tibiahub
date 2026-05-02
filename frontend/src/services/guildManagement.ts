// Guild Management API Service
import api from './api';

export interface GuildMember {
    id: number;
    username: string;
    email?: string;
    guild_rank?: string;
    is_active: boolean;
    is_superuser: boolean;
    join_date?: string;
    created_at: string;
    characters: {
        character_name: string;
        level?: number;
        vocation?: string;
        last_seen?: string;
    }[];
}

export interface SystemStats {
    total_users: number;
    active_users: number;
    inactive_users: number;
    admin_users: number;
    total_characters_linked: number;
    guild_ranks: { rank: string; count: number }[];
}

export interface TibiaAPIStatus {
    status: 'online' | 'offline' | 'degraded';
    latency_ms?: number;
    cached: boolean;
    last_check: string;
    message: string;
}

export interface SystemSettings {
    tibia_validation_enabled: boolean;
    tibia_validation_strict: boolean;
    discord_webhook_url: string;
    discord_auto_post: boolean;
    guild_raffles_enabled: boolean;
    guild_contests_enabled: boolean;
}

export interface GuildSyncResult {
    success: boolean;
    guild_name: string;
    total_members: number;
    synced_users: number;
    updated_characters: number;
    new_characters: number;
    invalid_users: Array<{
        user_id: number;
        username: string;
        character_name: string;
        reason: string;
    }>;
    message: string;
}

export const guildManagementApi = {
    getGuilds: async (): Promise<string[]> => {
        const response = await api.get('/guild-management/guilds');
        return response.data;
    },

    // Get all users
    getUsers: async (skip = 0, limit = 100): Promise<GuildMember[]> => {
        const response = await api.get(`/guild-management/users?skip=${skip}&limit=${limit}`);
        return response.data;
    },

    // Get user details
    getUserDetail: async (userId: number): Promise<GuildMember> => {
        const response = await api.get(`/guild-management/users/${userId}`);
        return response.data;
    },

    // Update user
    updateUser: async (userId: number, data: Partial<GuildMember>): Promise<GuildMember> => {
        const response = await api.put(`/guild-management/users/${userId}`, data);
        return response.data;
    },

    // Delete user
    deleteUser: async (userId: number): Promise<{ message: string }> => {
        const response = await api.delete(`/guild-management/users/${userId}`);
        return response.data;
    },

    // Update user character
    updateUserCharacter: async (userId: number, characterName: string): Promise<{
        success: boolean;
        message: string;
        character_name: string;
        validation_passed: boolean;
        validation_message?: string;
        character_data: { level?: number; vocation?: string };
    }> => {
        const response = await api.put(`/guild-management/users/${userId}/character?character_name=${encodeURIComponent(characterName)}`);
        return response.data;
    },

    // Get system stats
    getStats: async (): Promise<SystemStats> => {
        const response = await api.get('/guild-management/stats');
        return response.data;
    },

    // Get Tibia API status
    getTibiaAPIStatus: async (): Promise<TibiaAPIStatus> => {
        const response = await api.get('/guild-management/tibia-api-status');
        return response.data;
    },

    // Get system settings
    getSettings: async (): Promise<SystemSettings> => {
        const response = await api.get('/guild-management/settings');
        return response.data;
    },

    // Update system settings
    updateSettings: async (data: Partial<SystemSettings>): Promise<SystemSettings> => {
        const response = await api.put('/guild-management/settings', data);
        return response.data;
    },

    // Sync guild with Tibia API
    syncGuild: async (guildName = 'Ashclaw'): Promise<GuildSyncResult> => {
        const response = await api.post(`/guild-management/sync-guild?guild_name=${guildName}`);
        return response.data;
    },
};
