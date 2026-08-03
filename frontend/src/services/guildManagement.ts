// Guild Management API Service
import api, { ADMIN_ACTION_TIMEOUT_MS } from './api';

export interface GuildMember {
    id: number;
    username: string;
    display_name?: string;
    email?: string;
    avatar_url?: string;
    primary_character_id?: number;
    tibia_character_name?: string;
    world_name?: string;
    guild_name?: string;
    guild_rank?: string;
    is_active: boolean;
    is_superuser: boolean;
    is_moderator: boolean;
    is_writer: boolean;
    join_date?: string;
    created_at: string;
    characters: {
        id?: number;
        character_name: string;
        level?: number;
        vocation?: string;
        last_seen?: string;
    }[];
}

export interface AdminCharacterSearchResult {
    character_name: string; world_name?: string; guild_name?: string; guild_rank?: string;
    level?: number; vocation?: string; roster_character_id?: number; linked_user_id?: number; ownership_status?: string;
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
    latency_ms?: number | null;
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
    cyclopedia_category_images: Record<string, string>;
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
    unlinked_users: number;
    message: string;
}

export type GuildManagementCapability =
    | 'raffles.manage'
    | 'events.manage'
    | 'hunts.manage'
    | 'announcements.manage';

export interface ManageableGuildContext {
    capability: GuildManagementCapability;
    guilds: string[];
    guild_worlds: Record<string, string | null>;
}

export interface GuildManagementGrant {
    id: number;
    user_id: number;
    guild_name: string;
    capability: GuildManagementCapability;
    granted_by_id: number;
    granted_at: string;
    revoked_at: string | null;
}

export interface GuildAccessContext {
    guild_name: string;
    world_name: string | null;
    role: 'global_admin' | 'guild_leader' | 'guild_member' | 'delegated_manager';
    capabilities: Record<GuildManagementCapability, boolean>;
    can_grant_permissions: boolean;
    representative_character_name: string | null;
}

export const guildManagementApi = {
    searchCharacters: async (query: string): Promise<AdminCharacterSearchResult[]> =>
        (await api.get('/admin/character-ownership/search', { params: { query } })).data,

    linkCharacter: async (payload: { user_id: number; character_name: string; set_primary: boolean; allow_transfer: boolean; reason: string; confirmation: string }) =>
        (await api.post('/admin/character-ownership/link', payload, { timeout: ADMIN_ACTION_TIMEOUT_MS })).data,

    getGuildContext: async (): Promise<GuildAccessContext[]> => {
        const response = await api.get('/guild-management/context');
        return response.data.guilds;
    },

    getManageableGuilds: async (
        capability: GuildManagementCapability = 'raffles.manage'
    ): Promise<ManageableGuildContext> => {
        const response = await api.get('/guild-management/manageable-guilds', { params: { capability } });
        return response.data;
    },

    getGuildPermissions: async (guildName: string): Promise<GuildManagementGrant[]> => {
        const response = await api.get(`/guild-management/guilds/${encodeURIComponent(guildName)}/grants`);
        return response.data;
    },

    grantAllGuildPermissions: async (
        guildName: string,
        userId: number,
        reason?: string
    ): Promise<GuildManagementGrant[]> => {
        const response = await api.post(
            `/guild-management/guilds/${encodeURIComponent(guildName)}/grants`,
            { user_id: userId, grant_all: true, reason: reason || null }
        );
        return response.data;
    },

    revokeAllGuildPermissions: async (
        guildName: string,
        userId: number
    ): Promise<{ revoked: number }> => {
        const response = await api.post(
            `/guild-management/guilds/${encodeURIComponent(guildName)}/grants/${userId}/revoke`,
            { capabilities: null }
        );
        return response.data;
    },

    getGuilds: async (): Promise<string[]> => {
        const response = await api.get('/guild-management/guilds');
        return response.data;
    },

    // Get users with safe defaults (active, non-test accounts)
    getUsers: async (
        skip = 0,
        limit = 100,
        options?: { guild_name?: string; include_inactive?: boolean; exclude_test_accounts?: boolean }
    ): Promise<GuildMember[]> => {
        const params = new URLSearchParams();
        params.set('skip', String(skip));
        params.set('limit', String(limit));
        params.set('include_inactive', String(options?.include_inactive === true));
        params.set('exclude_test_accounts', String(options?.exclude_test_accounts !== false));
        if (options?.guild_name) {
            params.set('guild_name', options.guild_name);
        }
        const response = await api.get(`/guild-management/users?${params.toString()}`);
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

    uploadCategoryImage: async (category: string, file: File): Promise<{ category: string; image_url: string }> => {
        const form = new FormData();
        form.append('file', file);
        const response = await api.post(`/guild-management/settings/category-images/upload?category=${encodeURIComponent(category)}`, form, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            timeout: ADMIN_ACTION_TIMEOUT_MS,
        });
        return response.data;
    },

    // Sync guild with Tibia API
    syncGuild: async (guildName = 'Ashclaw'): Promise<GuildSyncResult> => {
        const response = await api.post(
            `/guild-management/sync-guild?guild_name=${guildName}`,
            undefined,
            { timeout: ADMIN_ACTION_TIMEOUT_MS }
        );
        return response.data;
    },
};
