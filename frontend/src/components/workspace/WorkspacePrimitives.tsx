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

/**
 * Section-level heading inside workspace content (renders <h2>, not <h1>).
 * Use this instead of WorkspaceHeader when titling a content section within
 * a page — WorkspaceHeader renders an h1 and is reserved for the shell level.
 */
export function WorkspaceContentHeader({ title, description, eyebrow, action, icon }: { title: string; description?: string; eyebrow?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <header className="workspace-content-header">
      <div className="workspace-content-header-copy">
        {eyebrow ? <p className="workspace-section-eyebrow">{eyebrow}</p> : null}
        <h2 className="workspace-section-header">
          {icon ? <span className="workspace-content-header-icon" aria-hidden="true">{icon}</span> : null}
          <span className="min-w-0">{title}</span>
        </h2>
        {description ? <p className="workspace-section-description">{description}</p> : null}
      </div>
      {action ? <div className="workspace-content-header-actions">{action}</div> : null}
    </header>
  );
}

export function WorkspaceShell({ navigation, pathname, header, children, variant }: { navigation: WorkspaceNavigationItem[]; pathname: string; header: ReactNode; children: ReactNode; variant: 'guild' | 'admin' }) {
  const { t } = useTranslation();
  return <div className="workspace-shell" data-workspace={variant}>
    {header}
    <div className="workspace-shell-body">
      <aside className="workspace-sidebar" aria-label={t(`workspace.${variant}.navigation`)}>
        <nav className="workspace-nav">
          {navigation.map(item => { const Icon = item.icon; const active = item.active ? item.active(pathname) : pathname === item.path; return <NavLink key={item.key} to={item.path} className="workspace-nav-link" data-active={active} aria-current={active ? 'page' : undefined}><Icon className="workspace-nav-icon" aria-hidden="true" /><span>{item.label}</span></NavLink>; })}
        </nav>
      </aside>
      <main className="workspace-content">{children}</main>
    </div>
  </div>;
}

export function AssistanceBanner({ guildName }: { guildName?: string }) {
  const { t } = useTranslation();
  return <section className="admin-panel-muted rounded-xl border-l-4 border-l-warning p-4 text-sm"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-warning" /><div><strong>{t('workspace.assistance.title')}</strong><p className="mt-1 text-content-muted">{guildName ? t('workspace.assistance.message', { guild: guildName }) : t('workspace.assistance.active')}</p><p className="mt-1 text-xs text-content-muted">{t('workspace.assistance.auditNotice')}</p></div></div><Link to="/admin/assistance" className="app-button-secondary app-button-sm mt-3 inline-flex items-center gap-2"><ArrowLeft className="h-4 w-4" />{t('workspace.assistance.return')}</Link></section>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <DesignEmptyState className="mx-auto max-w-xl rounded-2xl border border-dashed border-line" icon={<AlertCircle />} title={title} description={description} action={action && <div className="mt-2">{action}</div>} />;
}

export function PermissionDeniedState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <DesignEmptyState className="mx-auto max-w-xl rounded-2xl border border-warning/40 bg-warning-subtle" icon={<LockKeyhole />} title={title} description={description} action={action} />;
}

export function RoleBadge({ role }: { role: string }) { const { t } = useTranslation(); return <Badge tone="primary">{t(`workspace.roles.${role}`)}</Badge>; }

export function MobileSectionTabs({ tabs, active, onChange }: { tabs: Array<{ id: string; label: string }>; active: string; onChange: (id: string) => void }) { return <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1" role="tablist">{tabs.map(tab => <button key={tab.id} type="button" role="tab" aria-selected={active === tab.id} onClick={() => onChange(tab.id)} className={`min-h-11 shrink-0 snap-start rounded-lg px-4 text-sm ${active === tab.id ? 'app-button-primary font-semibold' : 'app-button-secondary'}`}>{tab.label}</button>)}</div>; }

export function PermissionGate({ allowed, children }: { allowed: boolean; children: ReactNode }) { return allowed ? <>{children}</> : null; }
