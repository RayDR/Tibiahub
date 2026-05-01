import api from './api';
import { User } from './auth';

export interface Announcement {
    id: number;
    title: string;
    content: string;
    type: 'general' | 'contest' | 'hunt';
    created_at: string;
    author?: User;
}

export interface Event {
    id: number;
    title: string;
    description: string;
    start_time: string;
    end_time?: string;
    type: 'quest' | 'hunt' | 'pvp' | 'meeting' | 'other';
    author?: User;
}

export interface Recruitment {
    id: number;
    recruit_name: string;
    status: 'pending' | 'accepted' | 'rejected';
    created_at: string;
    recruiter?: User;
}

export const guildApi = {
    getAnnouncements: async (skip: number = 0, limit: number = 10): Promise<Announcement[]> => {
        const response = await api.get('/guild/announcements', { params: { skip, limit } });
        return response.data;
    },

    createAnnouncement: async (data: { title: string; content: string; type: string }): Promise<Announcement> => {
        const response = await api.post('/guild/announcements', data);
        return response.data;
    },

    getEvents: async (skip: number = 0, limit: number = 20): Promise<Event[]> => {
        const response = await api.get('/guild/events', { params: { skip, limit } });
        return response.data;
    },

    createEvent: async (data: any): Promise<Event> => {
        const response = await api.post('/guild/events', data);
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
    }
};
