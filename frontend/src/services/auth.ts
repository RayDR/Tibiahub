import api, { LOGIN_TIMEOUT_MS } from './api';

export interface User {
    id: number;
    username: string;
    email?: string;
    avatar_url?: string;
    tibia_character_name?: string;
    guild_rank?: string;
    guild_name?: string;
    world_name?: string;
    residence?: string;
    vocation?: string;
    level?: number;
    achievement_points?: number;
    tibia_status?: string;
    is_active: boolean;
    is_superuser: boolean;
}

export interface AuthResponse {
    access_token: string;
    token_type: string;
}

export const authApi = {
    login: async (username: string, password: string): Promise<AuthResponse> => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        const response = await api.post('/auth/login', formData, {
            timeout: LOGIN_TIMEOUT_MS,
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    },

    register: async (data: { username: string; password: string; email?: string; tibia_character_name?: string }): Promise<User> => {
        const response = await api.post('/auth/register', data);
        return response.data;
    },

    getMe: async (): Promise<User> => {
        const response = await api.get('/auth/me');
        return response.data;
    }
};
