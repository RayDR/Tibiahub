import api from './api';
import type { AssistantLanguage, AssistantRequest, AssistantResponse, AssistantSuggestion } from '../types/assistant';

export const ASSISTANT_REQUEST_TIMEOUT_MS = 75000;

export const assistantApi = {
  suggestions: async (language: AssistantLanguage, signal?: AbortSignal): Promise<AssistantSuggestion[]> => {
    const response = await api.get('/assistant/suggestions', { params: { language, limit: 8 }, signal });
    return response.data;
  },
  ask: async (payload: AssistantRequest, signal?: AbortSignal): Promise<AssistantResponse> => {
    const response = await api.post('/assistant/', payload, {
      signal,
      timeout: ASSISTANT_REQUEST_TIMEOUT_MS,
      headers: payload.context?.conversation_id
        ? { 'X-Assistant-Session': payload.context.conversation_id }
        : undefined,
    });
    return response.data;
  },
};
