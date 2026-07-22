import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ChevronRight, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LeadershipApplication } from '../../services/leadership';

export function LeadershipBreadcrumbs({ candidate, adminBase }: { candidate?:string; adminBase?:string }) {
  const { t } = useTranslation(); const root=adminBase ? `${adminBase}/leadership` : '/guild/leadership';
  const items=[{label:t(adminBase?'leadership.breadcrumbs.assistedGuild':'leadership.breadcrumbs.myGuild'),to:adminBase||'/guild'},{label:t('leadership.navigation'),to:root},{label:t('leadership.recruitment.title'),to:`${root}/recruitment`}];
  return <nav aria-label={t('leadership.breadcrumbs.label')} className="flex min-w-0 items-center gap-1 overflow-hidden text-xs text-slate-400">{items.map((item,index)=><span key={item.to} className="flex min-w-0 items-center gap-1"><Link className="truncate rounded px-1 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400" to={item.to}>{item.label}</Link>{(index<items.length-1||candidate)&&<ChevronRight aria-hidden className="h-3 w-3 shrink-0" />}</span>)}{candidate&&<span aria-current="page" className="truncate text-slate-200">{candidate}</span>}</nav>;
}

export function LeadershipSkeleton({ cards=4 }: { cards?:number }) { return <div aria-label="" className="grid gap-3 sm:grid-cols-2">{Array.from({length:cards},(_,index)=><div key={index} className="h-28 animate-pulse rounded-xl bg-slate-900 motion-reduce:animate-none" />)}</div>; }

export function InlineError({ retry }: { retry:()=>void }) { const {t}=useTranslation(); return <div role="alert" className="flex flex-col gap-3 rounded-xl border border-amber-700/40 bg-amber-950/10 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-2"><AlertCircle aria-hidden className="h-5 w-5 shrink-0 text-amber-300"/><div><strong>{t('leadership.errors.section')}</strong><p className="text-sm text-slate-400">{t('leadership.errors.offline')}</p></div></div><button onClick={retry} className="min-h-11 rounded-lg border border-slate-700 px-4">{t('leadership.actions.retry')}</button></div>; }

export function StatusChip({ status }: { status:string }) { const {t}=useTranslation(); return <span className="inline-flex min-h-7 items-center rounded-full border border-slate-600 px-2.5 py-1 text-xs font-medium text-slate-200">{t(`leadership.status.${status}`)}</span>; }

export function LeadershipTimeline({ history }: { history:LeadershipApplication['history'] }) { const {t}=useTranslation(); return <ol className="space-y-3">{history.map((entry,index)=><li key={`${entry.created_at}-${index}`} className="relative border-l-2 border-amber-500/30 pb-2 pl-4 last:pb-0"><span aria-hidden className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-amber-400"/><div className="flex flex-wrap items-center gap-2"><strong className="text-sm">{t(`leadership.status.${entry.to_status}`)}</strong>{entry.admin_assistance&&<span className="inline-flex items-center gap-1 rounded-full bg-sky-950 px-2 py-1 text-[11px] text-sky-200"><ShieldCheck className="h-3 w-3"/>{t('leadership.timeline.adminAssistance')}</span>}</div><p className="text-xs text-slate-500"><time>{new Date(entry.created_at).toLocaleString()}</time>{entry.actor_name&&` · ${entry.actor_name}`}</p>{entry.reason&&<p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">{entry.reason}</p>}</li>)}</ol>; }

export function SectionCard({ title, icon, children, className='' }: {title:string;icon?:ReactNode;children:ReactNode;className?:string}) { return <section className={`space-y-3 rounded-xl border border-slate-800 bg-slate-950/20 p-4 ${className}`}><h2 className="flex items-center gap-2 text-base font-semibold">{icon}{title}</h2>{children}</section>; }
