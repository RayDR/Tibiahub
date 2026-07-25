import { ReactNode } from 'react';
import { AlertCircle, ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, EmptyState as DesignEmptyState, Panel } from '../ui';

export function WorkspaceHeader({ title, subtitle, badge, action }: { title: string; subtitle?: string; badge?: string; action?: ReactNode }) {
  return <Panel className="flex flex-col gap-3 rounded-2xl bg-surface-raised p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"><div><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-semibold sm:text-2xl">{title}</h1>{badge && <Badge tone="primary">{badge}</Badge>}</div>{subtitle && <p className="mt-1 text-sm text-content-muted">{subtitle}</p>}</div>{action}</Panel>;
}

export function AssistanceBanner({ guildName }: { guildName: string }) {
  const { t } = useTranslation();
  return <section className="admin-panel-muted rounded-xl p-4 text-sm"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><div><strong>{t('workspace.assistance.title')}</strong><p className="mt-1 text-content-muted">{t('workspace.assistance.message', { guild: guildName })}</p><p className="mt-1 text-xs text-content-muted">{t('workspace.assistance.auditNotice')}</p></div></div><Link to="/admin/guilds" className="admin-secondary mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg px-3 py-2"><ArrowLeft className="h-4 w-4" />{t('workspace.assistance.return')}</Link></section>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <DesignEmptyState className="mx-auto max-w-xl rounded-2xl border border-dashed border-line" icon={<AlertCircle />} title={title} description={description} action={action && <div className="mt-2">{action}</div>} />;
}

export function RoleBadge({ role }: { role: string }) { const { t } = useTranslation(); return <Badge tone="primary">{t(`workspace.roles.${role}`)}</Badge>; }

export function MobileSectionTabs({ tabs, active, onChange }: { tabs: Array<{ id: string; label: string }>; active: string; onChange: (id: string) => void }) { return <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1" role="tablist">{tabs.map(tab => <button key={tab.id} type="button" role="tab" aria-selected={active === tab.id} onClick={() => onChange(tab.id)} className={`min-h-11 shrink-0 snap-start rounded-lg px-4 text-sm ${active === tab.id ? 'admin-primary font-semibold' : 'admin-secondary'}`}>{tab.label}</button>)}</div>; }

export function PermissionGate({ allowed, children }: { allowed: boolean; children: ReactNode }) { return allowed ? <>{children}</> : null; }
