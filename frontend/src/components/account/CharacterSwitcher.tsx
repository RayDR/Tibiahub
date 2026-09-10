import { Check, ChevronDown, Search, ShieldCheck, UserRoundPlus, UsersRound } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { useActiveCharacter } from '../../context/ActiveCharacterContext';
import { useAuth } from '../../context/AuthContext';

export default function CharacterSwitcher() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const {
    activeCharacter,
    activeCharacterId,
    characters,
    loading,
    selectCharacter,
  } = useActiveCharacter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', close);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const visibleCharacters = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return characters;
    return characters.filter((character) => [
      character.character_name,
      character.world_name,
      character.vocation,
    ].some((value) => String(value || '').toLocaleLowerCase().includes(needle)));
  }, [characters, query]);

  if (!isAuthenticated) return null;

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        className="app-nav-link flex min-h-11 max-w-56 items-center gap-2 rounded-lg px-2 sm:px-3"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={t('characterProgress.switchCharacter')}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="grid size-8 shrink-0 place-items-center rounded-full border border-primary/30 bg-primary/10 text-primary">
          <UsersRound className="size-4" />
        </span>
        <span className="hidden min-w-0 text-left md:block">
          <span className="block truncate text-xs font-semibold text-content-primary">
            {activeCharacter?.character_name || (loading ? t('common.loading') : t('characterProgress.noCharacter'))}
          </span>
          {activeCharacter ? (
            <span className="block truncate text-[0.65rem] text-content-muted">
              {activeCharacter.level ? `Lv. ${activeCharacter.level}` : ''}
              {activeCharacter.level && activeCharacter.vocation ? ' · ' : ''}
              {activeCharacter.vocation || activeCharacter.world_name || ''}
            </span>
          ) : null}
        </span>
        <ChevronDown className={`hidden size-3.5 shrink-0 transition md:block ${open ? 'rotate-180' : ''}`} />
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t('characterProgress.selectorTitle')}
          className="ds-dropdown absolute right-0 top-full z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] p-2 shadow-2xl"
        >
          <div className="border-b border-line px-2 pb-2 pt-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">
              {t('characterProgress.selectorTitle')}
            </p>
            {activeCharacter ? (
              <p className="mt-1 truncate text-sm text-content-secondary">
                {t('characterProgress.activeCharacter', { character: activeCharacter.character_name })}
              </p>
            ) : null}
          </div>

          {characters.length > 6 ? (
            <label className="relative my-2 block">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('characterProgress.searchCharacters')}
                className="app-input min-h-10 w-full pl-9 text-sm"
                autoFocus
              />
            </label>
          ) : null}

          <div className="max-h-80 overflow-y-auto py-1">
            {visibleCharacters.map((character) => {
              const selected = character.id === activeCharacterId;
              return (
                <button
                  key={character.id}
                  type="button"
                  onClick={() => {
                    selectCharacter(character.id);
                    setOpen(false);
                  }}
                  className={`flex min-h-12 w-full items-center gap-3 rounded-lg px-3 text-left transition hover:bg-surface-hover ${selected ? 'bg-primary/10' : ''}`}
                >
                  <span className={`grid size-8 shrink-0 place-items-center rounded-full ${selected ? 'bg-primary/20 text-primary' : 'bg-surface-raised text-content-muted'}`}>
                    {selected ? <Check className="size-4" /> : <ShieldCheck className="size-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-content-primary">{character.character_name}</span>
                    <span className="block truncate text-xs text-content-muted">
                      {character.level ? `Lv. ${character.level}` : t('characterProgress.levelUnknown')}
                      {character.vocation ? ` · ${character.vocation}` : ''}
                      {character.world_name ? ` · ${character.world_name}` : ''}
                    </span>
                  </span>
                </button>
              );
            })}

            {!loading && characters.length === 0 ? (
              <div className="px-3 py-4 text-sm text-content-muted">
                <p>{t('characterProgress.noVerifiedCharacter')}</p>
              </div>
            ) : null}

            {!loading && characters.length > 0 && visibleCharacters.length === 0 ? (
              <p className="px-3 py-4 text-sm text-content-muted">{t('characterProgress.noCharacterMatches')}</p>
            ) : null}
          </div>

          <Link
            to="/profile?tab=characters"
            onClick={() => setOpen(false)}
            className="mt-1 flex min-h-11 items-center gap-2 border-t border-line px-3 pt-2 text-sm font-medium text-primary hover:underline"
          >
            <UserRoundPlus className="size-4" />
            {t('characterProgress.manageCharacters')}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
