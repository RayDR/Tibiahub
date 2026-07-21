import { ReactNode } from 'react';
import { AlertCircle, ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export function WorkspaceHeader({ title, subtitle, badge, action }: { title: string; subtitle?: string; badge?: string; action?: ReactNode }) {
  return <header className="flex flex-col gap-3 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-alt)] p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"><div><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-semibold sm:text-2xl">{title}</h1>{badge && <span className="rounded-full bg-[color:var(--color-primary)]/15 px-2.5 py-1 text-xs font-semibold text-[color:var(--color-primary)]">{badge}</span>}</div>{subtitle && <p className="mt-1 text-sm text-[color:var(--color-text-muted)]">{subtitle}</p>}</div>{action}</header>;
}

export function AssistanceBanner({ guildName }: { guildName: string }) {
  const { t } = useTranslation();
  return <section className="rounded-xl border border-sky-500/30 bg-sky-950/20 p-4 text-sm"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-sky-300" /><div><strong className="text-sky-100">{t('workspace.assistance.title')}</strong><p className="mt-1 text-slate-300">{t('workspace.assistance.message', { guild: guildName })}</p><p className="mt-1 text-xs text-slate-400">{t('workspace.assistance.auditNotice')}</p></div></div><Link to="/admin/guilds" className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg border border-sky-500/30 px-3 py-2 text-sky-200"><ArrowLeft className="h-4 w-4" />{t('workspace.assistance.return')}</Link></section>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <section className="mx-auto flex max-w-xl flex-col items-center rounded-2xl border border-dashed border-[color:var(--color-border)] p-8 text-center"><AlertCircle className="h-9 w-9 text-[color:var(--color-text-muted)]" /><h2 className="mt-3 text-lg font-semibold">{title}</h2><p className="mt-2 text-sm text-[color:var(--color-text-muted)]">{description}</p>{action && <div className="mt-5">{action}</div>}</section>;
}

export function RoleBadge({ role }: { role: string }) { const { t } = useTranslation(); return <span className="rounded-full border border-amber-500/30 px-2 py-1 text-xs text-amber-200">{t(`workspace.roles.${role}`)}</span>; }

export function MobileSectionTabs({ tabs, active, onChange }: { tabs: Array<{ id: string; label: string }>; active: string; onChange: (id: string) => void }) { return <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1" role="tablist">{tabs.map(tab => <button key={tab.id} type="button" role="tab" aria-selected={active === tab.id} onClick={() => onChange(tab.id)} className={`min-h-11 shrink-0 snap-start rounded-lg px-4 text-sm ${active === tab.id ? 'bg-amber-500 font-semibold text-slate-950' : 'border border-slate-700 text-slate-300'}`}>{tab.label}</button>)}</div>; }

export function PermissionGate({ allowed, children }: { allowed: boolean; children: ReactNode }) { return allowed ? <>{children}</> : null; }
