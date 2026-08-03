import { useEffect, useMemo, useState } from 'react';
import { Bell, CalendarClock, Coins, Compass, LayoutDashboard, Megaphone, Shield, UserPlus, UserRound, Users } from 'lucide-react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { LoadingState } from '../components/ui';
import { EmptyState, RoleBadge, WorkspaceHeader, WorkspaceShell } from '../components/workspace/WorkspacePrimitives';
import { useAuth } from '../context/AuthContext';
import { GuildAccessContext, guildManagementApi } from '../services/guildManagement';
import type { GuildLayoutContext } from '../utils/guildContext';

export default function GuildLayout() {
  const { t } = useTranslation();
  const { user, loading, isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [guilds, setGuilds] = useState<GuildAccessContext[]>([]);
  const [selectedGuild, setSelectedGuild] = useState('');
  const [loadingGuilds, setLoadingGuilds] = useState(true);
  const navItems = useMemo(() => [
    { key: 'dashboard', label: t('guild.dashboard'), path: '/guild/dashboard', icon: LayoutDashboard },
    { key: 'members', label: t('guild.members'), path: '/guild/members', icon: Users },
    { key: 'announcements', label: t('guild.announcements'), path: '/guild/announcements', icon: Megaphone },
    { key: 'events', label: t('guild.events'), path: '/guild/events', icon: CalendarClock },
    { key: 'raffles', label: t('workspace.raffles.title'), path: '/guild/raffles', icon: Coins, active: (value: string) => value.startsWith('/guild/raffle') },
    { key: 'leadership', label: t('leadership.navigation'), path: '/guild/leadership', icon: UserPlus, active: (value: string) => value.startsWith('/guild/leadership') },
    { key: 'hunts', label: t('guild.huntCatalog'), path: '/guild/hunts', icon: Compass },
    { key: 'notifications', label: t('notifications.title'), path: '/guild/notifications', icon: Bell },
  ], [t]);

  useEffect(() => {
    if (!isAuthenticated) {
      setLoadingGuilds(false);
      return;
    }
    let active = true;
    setLoadingGuilds(true);
    guildManagementApi.getGuildContext()
      .then(contexts => {
        if (!active) return;
        setGuilds(contexts);
        setSelectedGuild(current => {
          if (contexts.some(item => item.guild_name === current)) return current;
          const own = contexts.find(item => item.guild_name.toLocaleLowerCase() === (user?.guild_name || '').trim().toLocaleLowerCase());
          return own?.guild_name || contexts[0]?.guild_name || '';
        });
      })
      .catch(() => active && setGuilds([]))
      .finally(() => active && setLoadingGuilds(false));
    return () => { active = false; };
  }, [isAuthenticated, user?.guild_name]);

  if (loading || loadingGuilds) return <LoadingState className="my-8 rounded-xl border border-line" title={t('workspace.common.loading')} />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const context = guilds.find(item => item.guild_name === selectedGuild);
  if (!context) return <div className="py-8"><EmptyState title={t('workspace.noGuild.title')} description={t('workspace.noGuild.help')} action={<Link to="/profile" className="app-button-primary"><UserRound className="size-4" />{t('workspace.noGuild.profile')}</Link>} /></div>;

  const header = <WorkspaceHeader
    title={context.guild_name}
    subtitle={t('workspace.guild.context', { character: context.representative_character_name || user?.tibia_character_name || user?.username })}
    badge={t('workspace.guild.commandCenter')}
    icon={<span className="grid size-10 place-items-center rounded-lg bg-primary-subtle"><Shield className="size-5" /></span>}
    action={<div className="flex flex-wrap items-center gap-2">
      {guilds.length > 1 && <label className="grid gap-1 text-xs text-content-muted">
        <span>{t('workspace.guild.selectGuild')}</span>
        <select value={selectedGuild} onChange={event => setSelectedGuild(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface px-3 text-sm text-content-primary">
          {guilds.map(item => <option key={item.guild_name} value={item.guild_name}>{item.guild_name}</option>)}
        </select>
      </label>}
      <RoleBadge role={context.role} />
    </div>}
  />;

  return <WorkspaceShell navigation={navItems} pathname={pathname} header={header} variant="guild">
    <Outlet context={{ selectedGuild: context.guild_name, guildContext: context } satisfies GuildLayoutContext} />
  </WorkspaceShell>;
}
