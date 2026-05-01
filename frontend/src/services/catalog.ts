const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export interface CatalogItem {
  id: number;
  type: 'hunt' | 'quest' | 'custom';
  name: string;
  location: string;
  level_min?: number;
  level_max?: number;
  vocation?: string;
  exp_per_hour?: number;
  profit_per_hour?: number;
  creatures?: string;
  quest_reward?: string;
  quest_requirements?: string;
  strategy?: string;
  notes?: string;
  difficulty?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CatalogCreate {
  type: 'hunt' | 'quest' | 'custom';
  name: string;
  location: string;
  level_min?: number;
  level_max?: number;
  vocation?: string;
  exp_per_hour?: number;
  profit_per_hour?: number;
  creatures?: string;
  quest_reward?: string;
  quest_requirements?: string;
  strategy?: string;
  notes?: string;
  difficulty?: string;
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

export const catalogApi = {
  async getItems(type?: string, level_min?: number, level_max?: number, vocation?: string): Promise<CatalogItem[]> {
    const params = new URLSearchParams();
    if (type) params.append('type', type);
    if (level_min) params.append('level_min', level_min.toString());
    if (level_max) params.append('level_max', level_max.toString());
    if (vocation) params.append('vocation', vocation);

    const response = await fetch(`${API_URL}/catalog?${params}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch catalog items');
    }

    return response.json();
  },

  async getItem(id: number): Promise<CatalogItem> {
    const response = await fetch(`${API_URL}/catalog/${id}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch catalog item');
    }

    return response.json();
  },

  async createItem(item: CatalogCreate): Promise<CatalogItem> {
    const response = await fetch(`${API_URL}/catalog`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(item),
    });

    if (!response.ok) {
      throw new Error('Failed to create catalog item');
    }

    return response.json();
  },

  async updateItem(id: number, item: Partial<CatalogCreate>): Promise<CatalogItem> {
    const response = await fetch(`${API_URL}/catalog/${id}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(item),
    });

    if (!response.ok) {
      throw new Error('Failed to update catalog item');
    }

    return response.json();
  },

  async deleteItem(id: number): Promise<void> {
    const response = await fetch(`${API_URL}/catalog/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to delete catalog item');
    }
  },
};
