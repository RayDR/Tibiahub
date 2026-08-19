import api from './api';
import type { ItemSearchResult } from '../types';
import { cachedKnowledgeRead, knowledgeCacheKey } from './knowledgeRequestCache';

export type ItemBrowseSort = 'name' | 'category';
export type ItemBrowseOrder = 'asc' | 'desc';

export interface ItemCategoryFacet {
  value: string;
  count: number;
}

export interface ItemFacets {
  total: number;
  categories: ItemCategoryFacet[];
}

export const itemBrowserApi = {
  browse: async (
    params: {
      search?: string;
      category?: string;
      sort_by?: ItemBrowseSort;
      sort_order?: ItemBrowseOrder;
      skip?: number;
      limit?: number;
    } = {},
    signal?: AbortSignal,
  ): Promise<ItemSearchResult[]> => (
    cachedKnowledgeRead(
      knowledgeCacheKey('/items/browse', params),
      async () => {
        const response = await api.get('/items/browse', { params, signal });
        return response.data;
      },
    )
  ),

  getFacets: async (signal?: AbortSignal): Promise<ItemFacets> => (
    cachedKnowledgeRead('/items/facets', async () => {
      const response = await api.get('/items/facets', { signal });
      return response.data;
    })
  ),
};
