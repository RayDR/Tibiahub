import api from './api';
import type { QuestSearchResult } from '../types';

export type QuestBrowseSort = 'name' | 'min_level';
export type QuestBrowseOrder = 'asc' | 'desc';

export interface QuestBrowseResult extends QuestSearchResult {
  is_access_quest: boolean;
}

export interface QuestFacets {
  total: number;
  access_quests: number;
  minimum_level_known: number;
  minimum_level_min?: number | null;
  minimum_level_max?: number | null;
}

export const questBrowserApi = {
  browse: async (
    params: {
      search?: string;
      access_only?: boolean;
      sort_by?: QuestBrowseSort;
      sort_order?: QuestBrowseOrder;
      skip?: number;
      limit?: number;
    } = {},
    signal?: AbortSignal,
  ): Promise<QuestBrowseResult[]> => {
    const response = await api.get('/quests/browse', { params, signal });
    return response.data;
  },

  getFacets: async (signal?: AbortSignal): Promise<QuestFacets> => {
    const response = await api.get('/quests/facets', { signal });
    return response.data;
  },
};
