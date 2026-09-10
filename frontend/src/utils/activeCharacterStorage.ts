export const ACTIVE_CHARACTER_SESSION_KEY = 'tibiahub:active-character-id';

export function activeCharacterPreferenceKey(userId: number): string {
  return `tibiahub:user:${userId}:active-character`;
}

export function getActiveCharacterId(): number | null {
  try {
    const raw = sessionStorage.getItem(ACTIVE_CHARACTER_SESSION_KEY);
    if (!raw) return null;
    const value = Number(raw);
    return Number.isInteger(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function setActiveCharacterSessionId(characterId: number | null): void {
  try {
    if (characterId == null) sessionStorage.removeItem(ACTIVE_CHARACTER_SESSION_KEY);
    else sessionStorage.setItem(ACTIVE_CHARACTER_SESSION_KEY, String(characterId));
  } catch {
    // Browser storage is an optional bridge for non-React service calls.
  }
}

export function getPreferredCharacterId(userId: number): number | null {
  try {
    const raw = localStorage.getItem(activeCharacterPreferenceKey(userId));
    if (!raw) return null;
    const value = Number(raw);
    return Number.isInteger(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function setPreferredCharacterId(userId: number, characterId: number | null): void {
  try {
    const key = activeCharacterPreferenceKey(userId);
    if (characterId == null) localStorage.removeItem(key);
    else localStorage.setItem(key, String(characterId));
  } catch {
    // The active character still works for the current React lifetime.
  }
}
