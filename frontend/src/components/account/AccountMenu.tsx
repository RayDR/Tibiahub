import { KeyboardEvent, useEffect, useRef, useState } from 'react';
import { LogOut, Shield, UserRound, UsersRound, KeyRound, Castle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';

export default function AccountMenu() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const close = (restore = false) => { setOpen(false); if (restore) requestAnimationFrame(() => trigger.current?.focus()); };
  useEffect(() => {
    if (!open) return undefined;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) close(); };
    const escape = (event: globalThis.KeyboardEvent) => { if (event.key === 'Escape') close(true); };
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  useEffect(() => {
    if (open) requestAnimationFrame(() => root.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus());
  }, [open]);
  if (!user) return null;
  const menuKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]'));
    const current = items.indexOf(document.activeElement as HTMLElement);
    let next = current;
    if (event.key === 'ArrowDown') next = (current + 1) % items.length;
    else if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else return;
    event.preventDefault(); items[next]?.focus();
  };
  const links = [
    ['overview', UserRound, t('accountMenu.profile')], ['characters', UsersRound, t('accountMenu.characters')],
    ['security', KeyRound, t('accountMenu.security')], ['guilds', Castle, t('accountMenu.guilds')],
  ] as const;
  return <div ref={root} className="relative">
    <button ref={trigger} type="button" className="app-nav-link grid min-h-11 min-w-11 place-items-center overflow-hidden rounded-lg" aria-label={t('accountMenu.open')} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {user.avatar_url ? <img src={user.avatar_url} alt="" className="size-8 rounded-full object-cover" /> : <UserRound className="size-4" />}
    </button>
    {open && <div role="menu" aria-label={t('accountMenu.label')} onKeyDown={menuKey} className="ds-dropdown absolute right-0 top-full mt-2 w-64 p-2 shadow-xl">
      <div className="flex items-center gap-3 border-b border-line p-2">
        <div className="grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-surface-raised">{user.avatar_url ? <img src={user.avatar_url} alt="" className="size-full object-cover" /> : <UserRound className="size-5" />}</div>
        <div className="min-w-0"><p className="truncate font-medium">{user.display_name || user.username}</p><p className="truncate text-xs text-content-muted">@{user.username}</p></div>
      </div>
      {links.map(([tab, Icon, label]) => <Link key={tab} role="menuitem" to={`/profile?tab=${tab}`} onClick={() => close()} className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm hover:bg-surface-hover"><Icon className="size-4" />{label}</Link>)}
      {user.is_superuser && <Link role="menuitem" to="/admin" onClick={() => close()} className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm hover:bg-surface-hover"><Shield className="size-4" />{t('accountMenu.admin')}</Link>}
      <button role="menuitem" type="button" onClick={() => { close(); logout(); }} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-danger hover:bg-danger-subtle"><LogOut className="size-4" />{t('accountMenu.logout')}</button>
    </div>}
  </div>;
}
