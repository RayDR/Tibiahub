import { AlertCircle, Check, Loader2, Save, UserRoundPlus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { useActiveCharacter } from '../../context/ActiveCharacterContext';
import { useQuestProgress } from '../../context/QuestProgressContext';

export default function UnsavedQuestProgressBanner() {
  const { t } = useTranslation();
  const { activeCharacter, characters } = useActiveCharacter();
  const { pendingLocalCount, syncingLocal, syncLocalToActiveCharacter } = useQuestProgress();
  const [message, setMessage] = useState<'saved' | 'error' | null>(null);

  if (pendingLocalCount === 0) return null;

  const save = async () => {
    setMessage(null);
    try {
      await syncLocalToActiveCharacter();
      setMessage('saved');
    } catch {
      setMessage('error');
    }
  };

  return (
    <aside className="mb-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm" aria-live="polite">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-2.5">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-warning" />
          <div className="min-w-0">
            <p className="font-semibold text-content-primary">{t('characterProgress.unsavedTitle')}</p>
            <p className="mt-0.5 text-xs leading-5 text-content-secondary">
              {t('characterProgress.unsavedBody', { count: pendingLocalCount })}{' '}
              {!activeCharacter ? t('characterProgress.chooseCharacter') : null}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 pl-6 sm:pl-0">
          {activeCharacter ? (
            <button type="button" onClick={() => void save()} disabled={syncingLocal} className="app-button-secondary app-button-sm min-h-9">
              {syncingLocal ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              {syncingLocal ? t('characterProgress.saving') : t('characterProgress.saveToCharacter', { character: activeCharacter.character_name })}
            </button>
          ) : (
            <Link to="/profile?tab=characters" className="app-button-secondary app-button-sm min-h-9">
              <UserRoundPlus className="size-3.5" />
              {characters.length ? t('characterProgress.switchCharacter') : t('characterProgress.manageCharacters')}
            </Link>
          )}
        </div>
      </div>

      {message === 'saved' && activeCharacter ? (
        <p className="mt-2 flex items-center gap-1.5 pl-6 text-xs text-success"><Check className="size-3.5" />{t('characterProgress.saved', { character: activeCharacter.character_name })}</p>
      ) : null}
      {message === 'error' ? <p className="mt-2 pl-6 text-xs text-danger">{t('characterProgress.saveFailed')}</p> : null}
    </aside>
  );
}
