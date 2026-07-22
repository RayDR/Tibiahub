import { fetchJson } from './http';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export interface EventParticipant {
  id: number;
  event_id: number;
  user_id: number;
  assigned_number?: number;
  entry_data?: string;
  joined_at: string;
  username?: string;
}

export interface Event {
  id: number;
  uuid: string;
  public_code?: string;
  type: 'raffle' | 'contest' | 'hunt_event' | 'custom';
  title: string;
  description?: string;
  rules?: string;
  reward?: string;
  start_date?: string;
  end_date?: string;
  draw_date?: string;
  total_slots?: number;
  entry_cost?: string;
  winner_id?: number;
  winner_number?: number;
  is_drawn: boolean;
  status: 'active' | 'closed' | 'completed' | 'cancelled';
  is_active: boolean;
  is_public?: boolean;
  creator_id: number;
  creator_name?: string;
  winner_name?: string;
  announcement_id?: number;
  participants: EventParticipant[];
  participant_count: number;
  participant_mode?: string;
  guild_name?: string;
  guild_world?: string;
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  type: 'raffle' | 'contest' | 'hunt_event' | 'custom';
  title: string;
  description?: string;
  rules?: string;
  reward?: string;
  start_date?: string;
  end_date?: string;
  draw_date?: string;
  total_slots?: number;
  entry_cost?: string;
  status?: string;
  is_public?: boolean;
  participant_mode?: string;
  active_days_limit?: number;
  guild_name?: string;
  guild_world?: string;
}

export interface DrawWinnerResponse {
  success: boolean;
  winner_id: number;
  winner_name: string;
  winner_number?: number;
  total_participants: number;
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

export const eventsApi = {
  async getEvents(status?: string, type?: string, guildName?: string): Promise<Event[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (type) params.append('type', type);
    if (guildName) params.append('guild_name', guildName);

    return fetchJson<Event[]>(`${API_URL}/events?${params}`, {
      headers: getAuthHeaders(),
    });
  },

  async getEvent(id: number): Promise<Event> {
    return fetchJson<Event>(`${API_URL}/events/${id}`, {
      headers: getAuthHeaders(),
    });
  },

  async createEvent(event: EventCreate): Promise<Event> {
    return fetchJson<Event>(`${API_URL}/events`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(event),
      timeoutMode: 'admin',
    });
  },

  async updateEvent(id: number, event: Partial<EventCreate>): Promise<Event> {
    return fetchJson<Event>(`${API_URL}/events/${id}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(event),
      timeoutMode: 'admin',
    });
  },

  async deleteEvent(id: number): Promise<void> {
    await fetchJson(`${API_URL}/events/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },

  async joinEvent(id: number): Promise<EventParticipant> {
    return fetchJson<EventParticipant>(`${API_URL}/events/${id}/join`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
  },

  async drawWinner(id: number): Promise<DrawWinnerResponse> {
    return fetchJson<DrawWinnerResponse>(`${API_URL}/events/${id}/draw`, {
      method: 'POST',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },

  async getPublicEvent(uuid: string): Promise<Event> {
    return fetchJson<Event>(`${API_URL}/events/public/${uuid}`, {
      headers: { 'Content-Type': 'application/json' },
    });
  },

  async getPublicEventByCode(publicCode: string): Promise<Event> {
    return fetchJson<Event>(`${API_URL}/events/public/code/${publicCode}`, {
      headers: { 'Content-Type': 'application/json' },
    });
  },

  async getRaffleStatus(uuid: string): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${uuid}/raffle/status`, {
      headers: { 'Content-Type': 'application/json' },
    });
  },

  async autoDrawRaffle(uuid: string): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${uuid}/raffle/draw`, {
      method: 'POST',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },

  async addManualParticipant(eventId: number, participantData: { character_name: string }): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${eventId}/participants/manual`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(participantData),
      timeoutMode: 'admin',
    });
  },

  async loadGuildParticipants(eventId: number, force: boolean = false): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${eventId}/participants/load-guild?force=${force}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },

  async deleteParticipant(eventId: number, participantId: number): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${eventId}/participants/${participantId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },

  async excludeParticipant(eventId: number, participantId: number): Promise<any> {
    return fetchJson<any>(`${API_URL}/events/${eventId}/participants/${participantId}/exclude`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      timeoutMode: 'admin',
    });
  },
};
