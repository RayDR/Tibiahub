// Hunt Catalog API Service
import api from './api';

export interface Hunt {
    id: number;
    name: string;
    location: string;
    level_min: number;
    level_max: number;
    vocation: string | null;
    exp_per_hour: number | null;
    profit_per_hour: number | null;
    creatures: string;
    strategy: string | null;
    notes: string | null;
    created_at: string;
    updated_at: string;
}

export interface HuntCreate {
    name: string;
    location: string;
    level_min: number;
    level_max: number;
    vocation?: string;
    exp_per_hour?: number;
    profit_per_hour?: number;
    creatures: string;
    strategy?: string;
    notes?: string;
}

export const huntCatalogApi = {
    getHunts: async (filters?: {
        skip?: number;
        limit?: number;
        level_min?: number;
        level_max?: number;
        vocation?: string;
        location?: string;
    }): Promise<Hunt[]> => {
        const params = new URLSearchParams();
        if (filters) {
            Object.entries(filters).forEach(([key, value]) => {
                if (value !== undefined && value !== null) {
                    params.append(key, value.toString());
                }
            });
        }
        const response = await api.get(`/hunts?${params.toString()}`);
        return response.data;
    },

    getHunt: async (id: number): Promise<Hunt> => {
        const response = await api.get(`/hunts/${id}`);
        return response.data;
    },

    createHunt: async (hunt: HuntCreate): Promise<Hunt> => {
        const response = await api.post('/hunts', hunt);
        return response.data;
    },

    updateHunt: async (id: number, hunt: Partial<HuntCreate>): Promise<Hunt> => {
        const response = await api.put(`/hunts/${id}`, hunt);
        return response.data;
    },

    deleteHunt: async (id: number): Promise<{ message: string }> => {
        const response = await api.delete(`/hunts/${id}`);
        return response.data;
    },
};
