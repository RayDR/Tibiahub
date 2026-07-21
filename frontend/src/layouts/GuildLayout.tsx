import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, Megaphone, CalendarClock, Users, Compass, Coins, UserPlus, Bell, UserRound } from 'lucide-react';
import { EmptyState, RoleBadge, WorkspaceHeader } from '../components/workspace/WorkspacePrimitives';
import type { GuildLayoutContext } from '../utils/guildContext';

export default function GuildLayout() {
    const { t } = useTranslation();
    const { user, loading, isAuthenticated } = useAuth();
    const location = useLocation();
    const guildName = (user?.guild_name || '').trim();
    const rank = (user?.guild_rank || '').toLowerCase();
    const role = user?.is_superuser ? 'global_admin' : rank.includes('vice') || rank.includes('marshal') ? 'guild_viceleader' : rank.includes('leader') || rank.includes('alpha') ? 'guild_leader' : 'guild_member';
    const navItems = useMemo(() => [
        { name: t('guild.dashboard'), path: '/guild/dashboard', icon: LayoutDashboard },
        { name: t('guild.members'), path: '/guild/members', icon: Users },
        { name: t('guild.announcements'), path: '/guild/announcements', icon: Megaphone },
        { name: t('guild.events'), path: '/guild/events', icon: CalendarClock },
        { name: t('workspace.raffles.title'), path: '/guild/raffles', icon: Coins },
        { name: t('guild.recruitment'), path: '/guild/recruitment', icon: UserPlus },
        { name: t('guild.huntCatalog'), path: '/guild/hunts', icon: Compass },
        { name: t('notifications.title'), path: '/guild/notifications', icon: Bell },
    ], [t]);
    if (loading) return <div className="mt-20 text-center text-[color:var(--color-text-muted)]">{t('workspace.common.loading')}</div>;
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    if (!guildName) return <div className="mt-8"><EmptyState title={t('workspace.noGuild.title')} description={t('workspace.noGuild.help')} action={<Link to="/profile" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 font-semibold text-slate-950"><UserRound className="h-4 w-4" />{t('workspace.noGuild.profile')}</Link>} /></div>;
    return <div className="mt-4 space-y-4 sm:mt-8">
        <WorkspaceHeader title={guildName} subtitle={user?.tibia_character_name || user?.username} badge={t('workspace.guild.badge')} action={<RoleBadge role={role} />} />
        <nav className="-mx-2 flex snap-x gap-2 overflow-x-auto px-2 pb-1 lg:flex-wrap" aria-label={t('workspace.guild.navigation')}>
            {navItems.map(item => { const Icon = item.icon; const active = location.pathname === item.path || (item.path === '/guild/raffles' && location.pathname.startsWith('/guild/raffle')); return <Link key={item.path} to={item.path} className={`flex min-h-11 shrink-0 snap-start items-center gap-2 rounded-lg px-3 text-sm font-medium ${active ? 'bg-amber-500 text-slate-950' : 'border border-[color:var(--color-border)] text-[color:var(--color-text-muted)]'}`}><Icon className="h-4 w-4" />{item.name}</Link>; })}
        </nav>
        <main className="app-surface min-h-[500px] rounded-xl p-3 shadow-lg sm:p-6"><Outlet context={{ selectedGuild: guildName } satisfies GuildLayoutContext} /></main>
    </div>;
}
