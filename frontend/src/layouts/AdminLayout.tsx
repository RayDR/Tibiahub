import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Activity, Settings, Database, Shield, Wrench, CalendarDays, Users } from 'lucide-react';
import { WorkspaceHeader } from '../components/workspace/WorkspacePrimitives';

export default function AdminLayout() {
    const { t } = useTranslation(); const { user, loading, isAuthenticated } = useAuth(); const location = useLocation();
    if (loading) return <div className="mt-20 text-center text-content-muted">{t('workspace.admin.loading')}</div>;
    if (!isAuthenticated || !user?.is_superuser) return <Navigate to="/guild" replace />;
    const items = [
        { key: 'overview', path: '/admin/overview', icon: Activity }, { key: 'guilds', path: '/admin/guilds', icon: Shield },
        { key: 'users', path: '/admin/users', icon: Users }, { key: 'activities', path: '/admin/activities', icon: CalendarDays },
        { key: 'cyclopedia', path: '/admin/bestiary', icon: Database }, { key: 'operations', path: '/admin/data-tools', icon: Wrench },
        { key: 'settings', path: '/admin/settings', icon: Settings },
    ];
    return <div className="admin-shell mt-4 space-y-4 sm:mt-8">
        <WorkspaceHeader title={t('workspace.admin.title')} subtitle={user.username} badge={t('workspace.admin.badge')} />
        <nav className="-mx-2 flex snap-x gap-2 overflow-x-auto px-2 pb-1 lg:flex-wrap" aria-label={t('workspace.admin.navigation')}>
            {items.map(item => { const Icon = item.icon; const active = location.pathname === item.path || (item.key === 'guilds' && location.pathname.startsWith('/admin/guilds')); return <Link key={item.key} to={item.path} className={`flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-3 text-sm ${active ? 'admin-primary font-semibold' : 'admin-secondary'}`}><Icon className="h-4 w-4" />{t(`workspace.adminNav.${item.key}`)}</Link>; })}
        </nav>
        <main className="app-surface min-h-[500px] rounded-xl p-3 sm:p-6"><Outlet /></main>
    </div>;
}
