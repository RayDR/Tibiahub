import { useMemo } from 'react';
import { Bell, CalendarClock, Coins, Compass, LayoutDashboard, Megaphone, Shield, UserPlus, UserRound, Users } from 'lucide-react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { LoadingState } from '../components/ui';
import { EmptyState, RoleBadge, WorkspaceHeader, WorkspaceShell } from '../components/workspace/WorkspacePrimitives';
import { useAuth } from '../context/AuthContext';
import type { GuildLayoutContext } from '../utils/guildContext';

export default function GuildLayout() {
  const { t } = useTranslation();
  const { user, loading, isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const guildName = (user?.guild_name || '').trim();
  const rank = (user?.guild_rank || '').toLowerCase();
  const role = rank.includes('vice') || rank.includes('marshal') ? 'guild_viceleader' : rank.includes('leader') || rank.includes('alpha') ? 'guild_leader' : 'guild_member';
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

  if (loading) return <LoadingState className="my-8 rounded-xl border border-line" title={t('workspace.common.loading')} />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!guildName) return <div className="py-8"><EmptyState title={t('workspace.noGuild.title')} description={t('workspace.noGuild.help')} action={<Link to="/profile" className="app-button-primary"><UserRound className="size-4" />{t('workspace.noGuild.profile')}</Link>} /></div>;

  const header = <WorkspaceHeader
    title={guildName}
    subtitle={t('workspace.guild.context', { character: user?.tibia_character_name || user?.username })}
    badge={t('workspace.guild.commandCenter')}
    icon={<span className="grid size-10 place-items-center rounded-lg bg-primary-subtle"><Shield className="size-5" /></span>}
    action={<RoleBadge role={role} />}
  />;

  return <WorkspaceShell navigation={navItems} pathname={pathname} header={header} variant="guild">
    <Outlet context={{ selectedGuild: guildName } satisfies GuildLayoutContext} />
  </WorkspaceShell>;
}
