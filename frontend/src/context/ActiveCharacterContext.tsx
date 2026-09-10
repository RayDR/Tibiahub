import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { useAuth } from './AuthContext';
import { profileApi, type CharacterIdentity } from '../services/profile';
import {
  getPreferredCharacterId,
  setActiveCharacterSessionId,
  setPreferredCharacterId,
} from '../utils/activeCharacterStorage';

export const ACTIVE_CHARACTER_CHANGED_EVENT = 'tibiahub:active-character-changed';

interface ActiveCharacterContextValue {
  characters: CharacterIdentity[];
  activeCharacter: CharacterIdentity | null;
  activeCharacterId: number | null;
  loading: boolean;
  error: boolean;
  selectCharacter: (characterId: number) => void;
  refreshCharacters: () => Promise<void>;
}

const ActiveCharacterContext = createContext<ActiveCharacterContextValue | undefined>(undefined);

export function ActiveCharacterProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [characters, setCharacters] = useState<CharacterIdentity[]>([]);
  const [activeCharacterId, setActiveCharacterId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const applyProfile = useCallback((profileCharacters: CharacterIdentity[], primaryCharacterId?: number) => {
    if (!user) return;
    const verified = profileCharacters.filter((character) => character.ownership_status === 'verified');
    const remembered = getPreferredCharacterId(user.id);
    const preferred = verified.find((character) => character.id === remembered)
      || verified.find((character) => character.id === primaryCharacterId)
      || verified.find((character) => character.id === user.primary_character_id)
      || verified.find((character) => character.is_primary)
      || verified[0]
      || null;

    setCharacters(verified);
    setActiveCharacterId(preferred?.id || null);
    setActiveCharacterSessionId(preferred?.id || null);
    if (preferred) setPreferredCharacterId(user.id, preferred.id);
  }, [user]);

  const refreshCharacters = useCallback(async () => {
    if (!isAuthenticated || !user) {
      setCharacters([]);
      setActiveCharacterId(null);
      setActiveCharacterSessionId(null);
      setLoading(false);
      setError(false);
      return;
    }

    setLoading(true);
    setError(false);
    try {
      const profile = await profileApi.me();
      applyProfile(profile.character_details, profile.primary_character_id);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [applyProfile, isAuthenticated, user]);

  useEffect(() => {
    if (authLoading) return;
    let active = true;

    if (!isAuthenticated || !user) {
      setCharacters([]);
      setActiveCharacterId(null);
      setActiveCharacterSessionId(null);
      setLoading(false);
      setError(false);
      return;
    }

    setLoading(true);
    setError(false);
    void profileApi.me()
      .then((profile) => {
        if (active) applyProfile(profile.character_details, profile.primary_character_id);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [applyProfile, authLoading, isAuthenticated, user]);

  useEffect(() => () => setActiveCharacterSessionId(null), []);

  const selectCharacter = useCallback((characterId: number) => {
    if (!user) return;
    if (!characters.some((character) => character.id === characterId)) return;
    setActiveCharacterId(characterId);
    setActiveCharacterSessionId(characterId);
    setPreferredCharacterId(user.id, characterId);
    window.dispatchEvent(new CustomEvent(ACTIVE_CHARACTER_CHANGED_EVENT, { detail: { characterId } }));
  }, [characters, user]);

  const activeCharacter = useMemo(
    () => characters.find((character) => character.id === activeCharacterId) || null,
    [activeCharacterId, characters],
  );

  const value = useMemo<ActiveCharacterContextValue>(() => ({
    characters,
    activeCharacter,
    activeCharacterId,
    loading: authLoading || loading,
    error,
    selectCharacter,
    refreshCharacters,
  }), [activeCharacter, activeCharacterId, authLoading, characters, error, loading, refreshCharacters, selectCharacter]);

  return <ActiveCharacterContext.Provider value={value}>{children}</ActiveCharacterContext.Provider>;
}

export function useActiveCharacter(): ActiveCharacterContextValue {
  const context = useContext(ActiveCharacterContext);
  if (!context) throw new Error('useActiveCharacter must be used within ActiveCharacterProvider');
  return context;
}
