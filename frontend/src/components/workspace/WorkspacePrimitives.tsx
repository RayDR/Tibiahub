import { ReactNode } from 'react';
import { AlertCircle, ArrowLeft, LockKeyhole, ShieldCheck } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, EmptyState as DesignEmptyState, PageHeader } from '../ui';

export interface WorkspaceNavigationItem {
  key: string;
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  active?: (pathname: string) => boolean;
}

export function WorkspaceHeader({ title, subtitle, badge, action, icon, breadcrumbs }: { title: string; subtitle?: string; badge?: string; action?: ReactNode; icon?: ReactNode; breadcrumbs?: Array<{ label: string; to?: string }> }) {
  return <PageHeader contained size="md" title={title} subtitle={subtitle} eyebrow={badge} iconElement={icon} breadcrumbs={breadcrumbs} primaryAction={action} />;
}

export function WorkspaceShell({ navigation, pathname, header, children, variant }: { navigation: WorkspaceNavigationItem[]; pathname: string; header: ReactNode; children: ReactNode; variant: 'guild' | 'admin' }) {
  const { t } = useTranslation();
  return <div className="workspace-shell py-4 sm:py-6" data-workspace={variant}>
    {header}
    <div className="mt-4 grid min-w-0 gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="workspace-sidebar" aria-label={t(`workspace.${variant}.navigation`)}>
        <nav className="workspace-nav">
          {navigation.map(item => { const Icon = item.icon; const active = item.active ? item.active(pathname) : pathname === item.path; return <NavLink key={item.key} to={item.path} className="workspace-nav-link" data-active={active}><Icon className="size-4 shrink-0" /><span>{item.label}</span></NavLink>; })}
        </nav>
      </aside>
      <main className="workspace-content min-w-0">{children}</main>
    </div>
  </div>;
}

export function AssistanceBanner({ guildName }: { guildName?: string }) {
  const { t } = useTranslation();
  return <section className="admin-panel-muted rounded-xl border-l-4 border-l-warning p-4 text-sm"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-warning" /><div><strong>{t('workspace.assistance.title')}</strong><p className="mt-1 text-content-muted">{guildName ? t('workspace.assistance.message', { guild: guildName }) : t('workspace.assistance.active')}</p><p className="mt-1 text-xs text-content-muted">{t('workspace.assistance.auditNotice')}</p></div></div><Link to="/admin/assistance" className="admin-secondary mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg px-3 py-2"><ArrowLeft className="h-4 w-4" />{t('workspace.assistance.return')}</Link></section>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <DesignEmptyState className="mx-auto max-w-xl rounded-2xl border border-dashed border-line" icon={<AlertCircle />} title={title} description={description} action={action && <div className="mt-2">{action}</div>} />;
}

export function PermissionDeniedState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <DesignEmptyState className="mx-auto max-w-xl rounded-2xl border border-warning/40 bg-warning-subtle" icon={<LockKeyhole />} title={title} description={description} action={action} />;
}

export function RoleBadge({ role }: { role: string }) { const { t } = useTranslation(); return <Badge tone="primary">{t(`workspace.roles.${role}`)}</Badge>; }

export function MobileSectionTabs({ tabs, active, onChange }: { tabs: Array<{ id: string; label: string }>; active: string; onChange: (id: string) => void }) { return <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1" role="tablist">{tabs.map(tab => <button key={tab.id} type="button" role="tab" aria-selected={active === tab.id} onClick={() => onChange(tab.id)} className={`min-h-11 shrink-0 snap-start rounded-lg px-4 text-sm ${active === tab.id ? 'admin-primary font-semibold' : 'admin-secondary'}`}>{tab.label}</button>)}</div>; }

export function PermissionGate({ allowed, children }: { allowed: boolean; children: ReactNode }) { return allowed ? <>{children}</> : null; }
