import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ChevronRight, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LeadershipApplication } from '../../services/leadership';
import { Alert, Badge, Card, Skeleton } from '../ui';

export function LeadershipBreadcrumbs({ candidate, adminBase }: { candidate?:string; adminBase?:string }) {
  const { t } = useTranslation(); const root=adminBase ? `${adminBase}/leadership` : '/guild/leadership';
  const items=[{label:t(adminBase?'leadership.breadcrumbs.assistedGuild':'leadership.breadcrumbs.myGuild'),to:adminBase||'/guild'},{label:t('leadership.navigation'),to:root},{label:t('leadership.recruitment.title'),to:`${root}/recruitment`}];
  return <nav aria-label={t('leadership.breadcrumbs.label')} className="flex min-w-0 items-center gap-1 overflow-hidden text-xs text-content-secondary">{items.map((item,index)=><span key={item.to} className="flex min-w-0 items-center gap-1"><Link className="truncate rounded px-1 py-2 focus:outline-none focus:ring-2 focus:ring-primary" to={item.to}>{item.label}</Link>{(index<items.length-1||candidate)&&<ChevronRight aria-hidden className="h-3 w-3 shrink-0" />}</span>)}{candidate&&<span aria-current="page" className="truncate text-content-primary">{candidate}</span>}</nav>;
}

export function LeadershipSkeleton({ cards=4 }: { cards?:number }) { return <div aria-label="" className="grid gap-3 sm:grid-cols-2">{Array.from({length:cards},(_,index)=><Skeleton key={index} className="h-28 rounded-xl" />)}</div>; }

export function InlineError({ retry }: { retry:()=>void }) { const {t}=useTranslation(); return <Alert tone="warning" className="flex-col justify-between sm:flex-row sm:items-center"><div className="flex gap-2"><AlertCircle aria-hidden className="h-5 w-5 shrink-0"/><div><strong>{t('leadership.errors.section')}</strong><p className="text-sm text-content-secondary">{t('leadership.errors.offline')}</p></div></div><button onClick={retry} className="min-h-11 rounded-lg border border-line px-4">{t('leadership.actions.retry')}</button></Alert>; }

export function StatusChip({ status }: { status:string }) { const {t}=useTranslation(); return <Badge className="min-h-7">{t(`leadership.status.${status}`)}</Badge>; }

export function LeadershipTimeline({ history }: { history:LeadershipApplication['history'] }) { const {t}=useTranslation(); return <ol className="space-y-3">{history.map((entry,index)=><li key={`${entry.created_at}-${index}`} className="relative border-l-2 border-primary/30 pb-2 pl-4 last:pb-0"><span aria-hidden className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-primary"/><div className="flex flex-wrap items-center gap-2"><strong className="text-sm">{t(`leadership.status.${entry.to_status}`)}</strong>{entry.admin_assistance&&<Badge tone="info"><ShieldCheck className="h-3 w-3"/>{t('leadership.timeline.adminAssistance')}</Badge>}</div><p className="text-xs text-content-muted"><time>{new Date(entry.created_at).toLocaleString()}</time>{entry.actor_name&&` · ${entry.actor_name}`}</p>{entry.reason&&<p className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{entry.reason}</p>}</li>)}</ol>; }

export function SectionCard({ title, icon, children, className='' }: {title:string;icon?:ReactNode;children:ReactNode;className?:string}) { return <Card className={`space-y-3 bg-surface-base/20 p-4 ${className}`}><h2 className="flex items-center gap-2 text-base font-semibold">{icon}{title}</h2>{children}</Card>; }
