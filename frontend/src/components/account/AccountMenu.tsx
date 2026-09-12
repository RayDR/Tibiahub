import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, LogOut, Search, Shield, UserRound, UsersRound, KeyRound, Castle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useActiveCharacter } from '../../context/ActiveCharacterContext';
import { useAppearance } from '../../context/AppearanceContext';
import { useAuth } from '../../context/AuthContext';

export default function AccountMenu() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { layout } = useAppearance();
  const {
    activeCharacter,
    activeCharacterId,
    characters,
    loading: charactersLoading,
    selectCharacter,
  } = useActiveCharacter();
  const compactLayout = layout === 'compact';
  const [open, setOpen] = useState(false);
  const [charactersOpen, setCharactersOpen] = useState(false);
  const [query, setQuery] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const close = (restore = false) => {
    setOpen(false);
    setCharactersOpen(false);
    setQuery('');
    if (restore) requestAnimationFrame(() => trigger.current?.focus());
  };

  useEffect(() => {
    if (!open) return undefined;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') close(true);
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  useEffect(() => {
    if (open) requestAnimationFrame(() => root.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus());
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

  if (!user) return null;

  const menuKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target instanceof HTMLInputElement) return;
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]'));
    const current = items.indexOf(document.activeElement as HTMLElement);
    let next = current;
    if (event.key === 'ArrowDown') next = (current + 1) % items.length;
    else if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else return;
    event.preventDefault();
    items[next]?.focus();
  };

  const links = [
    ['overview', UserRound, t('accountMenu.profile')],
    ['characters', UsersRound, t('accountMenu.characters')],
    ['security', KeyRound, t('accountMenu.security')],
    ['guilds', Castle, t('accountMenu.guilds')],
  ] as const;

  const profileLabel = activeCharacter?.character_name || user.display_name || user.username;

  return (
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        className={`app-nav-link min-h-11 rounded-lg ${compactLayout ? 'flex max-w-44 items-center gap-2 px-2' : 'grid min-w-11 place-items-center overflow-hidden'}`}
        aria-label={t('accountMenu.open')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="size-8 shrink-0 rounded-full object-cover" />
        ) : (
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-raised">
            <UserRound className="size-4" />
          </span>
        )}
        {compactLayout ? (
          <>
            <span className="hidden min-w-0 flex-1 truncate text-left text-xs font-semibold text-content-primary lg:block">
              {profileLabel}
            </span>
            <ChevronDown className={`hidden size-3.5 shrink-0 text-content-muted transition lg:block ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
          </>
        ) : null}
      </button>

      {open ? (
        <div
          role="menu"
          aria-label={t('accountMenu.label')}
          onKeyDown={menuKey}
          className="ds-dropdown absolute right-0 top-full mt-2 w-[min(20rem,calc(100vw-2rem))] p-2 shadow-xl"
        >
          <div className="flex items-center gap-3 border-b border-line p-2">
            <div className="grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-surface-raised">
              {user.avatar_url ? <img src={user.avatar_url} alt="" className="size-full object-cover" /> : <UserRound className="size-5" />}
            </div>
            <div className="min-w-0">
              <p className="truncate font-medium">{user.display_name || user.username}</p>
              <p className="truncate text-xs text-content-muted">@{user.username}</p>
            </div>
          </div>

          {compactLayout ? (
            <div className="border-b border-line py-1">
              <button
                role="menuitem"
                type="button"
                onClick={() => setCharactersOpen((value) => !value)}
                className="flex min-h-12 w-full items-center gap-3 rounded-lg px-3 text-left hover:bg-surface-hover"
                aria-expanded={charactersOpen}
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-full border border-primary/30 bg-primary/10 text-primary">
                  <UsersRound className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-content-primary">
                    {activeCharacter?.character_name || t('characterProgress.noCharacter')}
                  </span>
                  <span className="block truncate text-xs text-content-muted">
                    {activeCharacter?.level ? `Lv. ${activeCharacter.level}` : t('characterProgress.switchCharacter')}
                    {activeCharacter?.vocation ? ` · ${activeCharacter.vocation}` : ''}
                  </span>
                </span>
                <ChevronDown className={`size-4 shrink-0 text-content-muted transition ${charactersOpen ? 'rotate-180' : ''}`} />
              </button>

              {charactersOpen ? (
                <div className="px-1 pb-2">
                  {characters.length > 6 ? (
                    <label className="relative my-2 block">
                      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
                      <input
                        type="search"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder={t('characterProgress.searchCharacters')}
                        className="app-input min-h-10 w-full pl-9 text-sm"
                      />
                    </label>
                  ) : null}

                  <div className="max-h-56 overflow-y-auto overscroll-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                    {visibleCharacters.map((character) => {
                      const selected = character.id === activeCharacterId;
                      return (
                        <button
                          key={character.id}
                          type="button"
                          onClick={() => {
                            selectCharacter(character.id);
                            close();
                          }}
                          className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-surface-hover ${selected ? 'bg-primary/10' : ''}`}
                        >
                          <span className={`grid size-7 shrink-0 place-items-center rounded-full ${selected ? 'bg-primary/20 text-primary' : 'bg-surface-raised text-content-muted'}`}>
                            {selected ? <Check className="size-3.5" /> : <UsersRound className="size-3.5" />}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-content-primary">{character.character_name}</span>
                            <span className="block truncate text-[0.65rem] text-content-muted">
                              {character.level ? `Lv. ${character.level}` : t('characterProgress.levelUnknown')}
                              {character.vocation ? ` · ${character.vocation}` : ''}
                              {character.world_name ? ` · ${character.world_name}` : ''}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                    {!charactersLoading && characters.length === 0 ? (
                      <p className="px-2 py-3 text-xs text-content-muted">{t('characterProgress.noVerifiedCharacter')}</p>
                    ) : null}
                    {!charactersLoading && characters.length > 0 && visibleCharacters.length === 0 ? (
                      <p className="px-2 py-3 text-xs text-content-muted">{t('characterProgress.noCharacterMatches')}</p>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {links.map(([tab, Icon, label]) => (
            <Link key={tab} role="menuitem" to={`/profile?tab=${tab}`} onClick={() => close()} className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm hover:bg-surface-hover">
              <Icon className="size-4" />{label}
            </Link>
          ))}
          {user.is_superuser ? (
            <Link role="menuitem" to="/admin" onClick={() => close()} className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm hover:bg-surface-hover">
              <Shield className="size-4" />{t('accountMenu.admin')}
            </Link>
          ) : null}
          <button role="menuitem" type="button" onClick={() => { close(); logout(); }} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-danger hover:bg-danger-subtle">
            <LogOut className="size-4" />{t('accountMenu.logout')}
          </button>
        </div>
      ) : null}
    </div>
  );
}
