const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

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
  async getEvents(status?: string, type?: string): Promise<Event[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (type) params.append('type', type);

    const response = await fetch(`${API_URL}/events?${params}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch events');
    }

    return response.json();
  },

  async getEvent(id: number): Promise<Event> {
    const response = await fetch(`${API_URL}/events/${id}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch event');
    }

    return response.json();
  },

  async createEvent(event: EventCreate): Promise<Event> {
    const response = await fetch(`${API_URL}/events`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      throw new Error('Failed to create event');
    }

    return response.json();
  },

  async updateEvent(id: number, event: Partial<EventCreate>): Promise<Event> {
    const response = await fetch(`${API_URL}/events/${id}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      throw new Error('Failed to update event');
    }

    return response.json();
  },

  async deleteEvent(id: number): Promise<void> {
    const response = await fetch(`${API_URL}/events/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to delete event');
    }
  },

  async joinEvent(id: number): Promise<EventParticipant> {
    const response = await fetch(`${API_URL}/events/${id}/join`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to join event');
    }

    return response.json();
  },

  async drawWinner(id: number): Promise<DrawWinnerResponse> {
    const response = await fetch(`${API_URL}/events/${id}/draw`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to draw winner');
    }

    return response.json();
  },

  async getPublicEvent(uuid: string): Promise<Event> {
    const response = await fetch(`${API_URL}/events/public/${uuid}`, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error('Failed to fetch public event');
    return response.json();
  },

  async getRaffleStatus(uuid: string): Promise<any> {
    const response = await fetch(`${API_URL}/events/${uuid}/raffle/status`, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error('Failed to fetch status');
    return response.json();
  },

  async autoDrawRaffle(uuid: string): Promise<any> {
    const response = await fetch(`${API_URL}/events/${uuid}/raffle/draw`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to auto draw');
    return response.json();
  },

  async addManualParticipant(eventId: number, participantData: { character_name: string }): Promise<any> {
    const response = await fetch(`${API_URL}/events/${eventId}/participants/manual`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(participantData),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to add participant');
    }
    return response.json();
  },

  async loadGuildParticipants(eventId: number, force: boolean = false): Promise<any> {
    const response = await fetch(`${API_URL}/events/${eventId}/participants/load-guild?force=${force}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to load guild participants');
    }
    return response.json();
  },

  async deleteParticipant(eventId: number, participantId: number): Promise<any> {
    const response = await fetch(`${API_URL}/events/${eventId}/participants/${participantId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete participant');
    }
    return response.json();
  },

  async excludeParticipant(eventId: number, participantId: number): Promise<any> {
    const response = await fetch(`${API_URL}/events/${eventId}/participants/${participantId}/exclude`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to exclude participant');
    }
    return response.json();
  },
};
