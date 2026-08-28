import { Check, Loader2, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { useAuth } from '../../context/AuthContext';
import { profileApi, type CharacterIdentity } from '../../services/profile';
import { questProgressApi } from '../../services/questProgress';

function storageKey(questKey: string) {
  return `tibiahub:quest-completion:${questKey}`;
}

function readSessionCompletion(questKey: string): boolean {
  try {
    return sessionStorage.getItem(storageKey(questKey)) === '1';
  } catch {
    return false;
  }
}

function writeSessionCompletion(questKey: string, completed: boolean) {
  try {
    if (completed) sessionStorage.setItem(storageKey(questKey), '1');
    else sessionStorage.removeItem(storageKey(questKey));
  } catch {
    // Session storage is optional.
  }
}

export default function QuestCompletionControl({
  questId,
  questSlug,
}: {
  questId: number;
  questSlug?: string;
}) {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const questKey = questSlug || String(questId);
  const [characters, setCharacters] = useState<CharacterIdentity[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | null>(null);
  const [completed, setCompleted] = useState(() => readSessionCompletion(questKey));
  const [loading, setLoading] = useState(isAuthenticated);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCharacter = useMemo(
    () => characters.find((character) => character.id === selectedCharacterId) || null,
    [characters, selectedCharacterId],
  );

  useEffect(() => {
    setCompleted(readSessionCompletion(questKey));
  }, [questKey]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCharacters([]);
      setSelectedCharacterId(null);
      setLoading(false);
      setError(null);
      return undefined;
    }

    const controller = new AbortController();
    let current = true;
    setLoading(true);
    setError(null);
    void profileApi.me().then(async (profile) => {
      if (!current) return;
      const verified = profile.character_details.filter((character) => character.ownership_status === 'verified');
      setCharacters(verified);
      const preferred = verified.find((character) => character.id === (profile.primary_character_id || user?.primary_character_id)) || verified[0] || null;
      setSelectedCharacterId(preferred?.id || null);
      if (!preferred) {
        setCompleted(readSessionCompletion(questKey));
        return;
      }
      const state = await questProgressApi.get(questSlug || questId, preferred.id, controller.signal);
      if (current) setCompleted(state.completed);
    }).catch(() => {
      if (!current || controller.signal.aborted) return;
      setCharacters([]);
      setSelectedCharacterId(null);
      setCompleted(readSessionCompletion(questKey));
      setError(t('questEnhancement.progressLoadError'));
    }).finally(() => {
      if (current) setLoading(false);
    });

    return () => {
      current = false;
      controller.abort();
    };
  }, [isAuthenticated, questId, questKey, questSlug, t, user?.primary_character_id]);

  const selectCharacter = async (characterId: number) => {
    setSelectedCharacterId(characterId);
    setLoading(true);
    setError(null);
    try {
      const state = await questProgressApi.get(questSlug || questId, characterId);
      setCompleted(state.completed);
    } catch {
      setError(t('questEnhancement.progressLoadError'));
    } finally {
      setLoading(false);
    }
  };

  const toggle = async () => {
    if (saving || loading) return;
    const next = !completed;
    setSaving(true);
    setError(null);
    try {
      if (isAuthenticated && selectedCharacterId != null) {
        const state = await questProgressApi.set(questSlug || questId, selectedCharacterId, next);
        setCompleted(state.completed);
      } else {
        writeSessionCompletion(questKey, next);
        setCompleted(next);
      }
    } catch {
      setError(t('questEnhancement.progressSaveError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="quest-codex__progress mt-6 rounded-xl border p-3 sm:p-4" aria-label={t('questEnhancement.progress')}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide">{t('questEnhancement.progress')}</p>
          <p className="mt-1 text-sm">
            {selectedCharacter
              ? t('questEnhancement.savedFor', { character: selectedCharacter.character_name })
              : t('questEnhancement.sessionOnly')}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {characters.length > 1 ? (
            <label className="flex items-center gap-2 text-xs">
              <span>{t('questEnhancement.selectCharacter')}</span>
              <select
                className="ds-select min-w-40"
                value={selectedCharacterId || ''}
                onChange={(event) => void selectCharacter(Number(event.target.value))}
                disabled={loading || saving}
              >
                {characters.map((character) => <option key={character.id} value={character.id}>{character.character_name}</option>)}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            onClick={() => void toggle()}
            disabled={loading || saving}
            className={completed ? 'app-button-secondary min-h-11' : 'app-button-primary min-h-11'}
            aria-pressed={completed}
          >
            {loading || saving ? <Loader2 className="size-4 animate-spin" /> : completed ? <RotateCcw className="size-4" /> : <Check className="size-4" />}
            {completed ? t('questEnhancement.markIncomplete') : t('questEnhancement.markComplete')}
          </button>
        </div>
      </div>

      {!selectedCharacter ? <p className="mt-2 text-xs opacity-75">{isAuthenticated ? t('questEnhancement.noVerifiedCharacter') : t('questEnhancement.sessionHelp')}</p> : null}
      {error ? <p className="mt-2 text-xs text-danger">{error}</p> : null}
    </section>
  );
}
