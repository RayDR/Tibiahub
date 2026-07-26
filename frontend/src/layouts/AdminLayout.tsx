import { Activity, BookOpenCheck, ClipboardList, LifeBuoy, Palette, RefreshCw, Settings, Shield, Users, Wrench } from 'lucide-react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { LoadingState } from '../components/ui';
import { AssistanceBanner, PermissionDeniedState, WorkspaceHeader, WorkspaceShell } from '../components/workspace/WorkspacePrimitives';
import { useAuth } from '../context/AuthContext';

export default function AdminLayout() {
  const { t } = useTranslation();
  const { user, loading, isAuthenticated } = useAuth();
  const { pathname } = useLocation();

  if (loading) return <LoadingState className="my-8 rounded-xl border border-line" title={t('workspace.admin.loading')} />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_superuser) return <div className="py-8"><PermissionDeniedState title={t('workspace.permission.title')} description={t('workspace.permission.admin')} action={<Link to="/guild" className="app-button-secondary">{t('workspace.permission.return')}</Link>} /></div>;

  const items = [
    { key: 'overview', label: t('workspace.adminNav.overview'), path: '/admin/overview', icon: Activity },
    { key: 'users', label: t('workspace.adminNav.users'), path: '/admin/users', icon: Users },
    { key: 'guilds', label: t('workspace.adminNav.guilds'), path: '/admin/guilds', icon: Shield, active: (value: string) => value === '/admin/guilds' },
    { key: 'assistance', label: t('workspace.adminNav.assistance'), path: '/admin/assistance', icon: LifeBuoy, active: (value: string) => value.startsWith('/admin/assistance') || /^\/admin\/guilds\/.+/.test(value) },
    { key: 'knowledge', label: t('workspace.adminNav.knowledge'), path: '/admin/knowledge', icon: BookOpenCheck },
    { key: 'sync', label: t('workspace.adminNav.sync'), path: '/admin/sync', icon: RefreshCw },
    { key: 'audits', label: t('workspace.adminNav.audits'), path: '/admin/audits', icon: ClipboardList },
    { key: 'maintenance', label: t('workspace.adminNav.maintenance'), path: '/admin/maintenance', icon: Wrench },
    { key: 'settings', label: t('workspace.adminNav.settings'), path: '/admin/settings', icon: Settings },
    { key: 'appearance', label: t('workspace.adminNav.appearance'), path: '/admin/theme-playground', icon: Palette },
  ];
  const detailOwnsAssistanceBanner = pathname.includes('/leadership/recruitment/applications/');
  const assistanceActive = /^\/admin\/guilds\/.+/.test(pathname) && !detailOwnsAssistanceBanner;
  const header = <WorkspaceHeader title={t('workspace.admin.title')} subtitle={t('workspace.admin.context', { username: user.username })} badge={t('workspace.admin.controlCenter')} icon={<span className="grid size-10 place-items-center rounded-lg bg-danger-subtle"><Shield className="size-5 text-danger" /></span>} />;

  return <WorkspaceShell navigation={items} pathname={pathname} header={header} variant="admin">
    {assistanceActive ? <div className="mb-4"><AssistanceBanner /></div> : null}
    <Outlet />
  </WorkspaceShell>;
}
