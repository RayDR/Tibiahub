import type { AssistantSuggestion } from '../types/assistant';

export function findSuggestionCompletion(
  value: string,
  suggestions: AssistantSuggestion[],
): AssistantSuggestion | null {
  const typed = value.trimStart();
  if (!typed) return null;
  const normalized = typed.toLocaleLowerCase();
  return suggestions.find((suggestion) => (
    suggestion.text.length > typed.length
    && suggestion.text.toLocaleLowerCase().startsWith(normalized)
  )) ?? null;
}

function stableHash(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

export function selectVisibleSuggestions(
  suggestions: AssistantSuggestion[],
  seed: string,
  limit = 3,
): AssistantSuggestion[] {
  if (suggestions.length <= limit) return suggestions;
  const start = stableHash(seed) % suggestions.length;
  const rotated = [...suggestions.slice(start), ...suggestions.slice(0, start)];
  const selected: AssistantSuggestion[] = [];
  for (const suggestion of rotated) {
    if (!selected.some((row) => row.entity_type === suggestion.entity_type)) selected.push(suggestion);
    if (selected.length === limit) return selected;
  }
  for (const suggestion of rotated) {
    if (!selected.some((row) => row.id === suggestion.id)) selected.push(suggestion);
    if (selected.length === limit) break;
  }
  return selected;
}
