import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Clock3, MessageSquare, ShieldCheck, Vote } from 'lucide-react';
import { AssistanceBanner, EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import { ApplicationStatus, LeadershipApplication, LeadershipSummary, leadershipApi } from '../../services/leadership';

const activeStatuses: ApplicationStatus[] = ['applied', 'under_review', 'more_information_requested', 'interview', 'voting'];

export default function LeadershipApplicationDetail({ admin = false }: { admin?: boolean }) {
  const { t } = useTranslation();
  const params = useParams();
  const guildKey = admin ? params.guildKey : undefined;
  const applicationId = Number(params.applicationId);
  const [application, setApplication] = useState<LeadershipApplication | null>(null);
  const [summary, setSummary] = useState<LeadershipSummary | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setError(false);
    try {
      const [nextApplication, nextSummary] = await Promise.all([leadershipApi.application(applicationId, guildKey), leadershipApi.summary(guildKey)]);
      setApplication(nextApplication); setSummary(nextSummary);
    } catch { setError(true); }
  };
  useEffect(() => { void load(); }, [applicationId, guildKey]);
  const action = async (work: () => Promise<unknown>) => { if (busy) return; setBusy(true); try { await work(); await load(); } finally { setBusy(false); } };
  if (error) return <EmptyState title={t('leadership.errors.load')} description={t('leadership.errors.retry')} action={<button onClick={() => void load()} className="min-h-11 rounded-lg border border-slate-700 px-4">{t('leadership.actions.retry')}</button>} />;
  if (!application || !summary) return <div className="p-8 text-center text-slate-400">{t('leadership.loading')}</div>;
  const reviewer = summary.capabilities.review && Boolean(application.answers);
  return <div className="space-y-4">
    {admin && <AssistanceBanner guildName={summary.guild_name} />}
    <WorkspaceHeader title={application.character_name} subtitle={t(`leadership.status.${application.status}`)} badge={t('leadership.applications.candidate')} />
    <section className="grid gap-3 rounded-xl border border-slate-800 p-4 sm:grid-cols-2 lg:grid-cols-4">
      {Object.entries(application.profile).filter(([, value]) => value !== null && value !== '').map(([key, value]) => <div key={key} className="min-w-0"><span className="block text-xs text-slate-500">{t(`leadership.fields.${key}`)}</span><strong className="block truncate">{String(value)}</strong></div>)}
    </section>
    {reviewer && application.answers && <Section icon={<ShieldCheck />} title={t('leadership.applications.answers')}>{Object.entries(application.answers).filter(([, value]) => value).map(([key, value]) => <div key={key} className="rounded-lg bg-slate-950 p-3"><strong className="text-sm">{t(`leadership.questions.${key}`)}</strong><p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">{value}</p></div>)}</Section>}
    <Section icon={<Clock3 />} title={t('leadership.applications.timeline')}>{application.history.map((entry, index) => <div key={`${entry.created_at}-${index}`} className="border-l-2 border-amber-500/30 pl-3"><strong className="text-sm">{t(`leadership.status.${entry.to_status}`)}</strong><p className="text-xs text-slate-500">{new Date(entry.created_at).toLocaleString()}</p>{entry.reason && <p className="mt-1 text-sm text-slate-300">{entry.reason}</p>}</div>)}</Section>
    <Section icon={<MessageSquare />} title={t('leadership.applications.communication')}>{application.messages.filter(item => item.audience !== 'reviewers').map(item => <Message key={item.id} item={item} />)}<MessageForm applicant={!reviewer} onSubmit={(body) => action(() => leadershipApi.message(application.id, { audience: reviewer ? 'applicant' : 'reviewers', message_type: reviewer ? 'information_request' : 'applicant_reply', body }, guildKey))} /></Section>
    {reviewer && <Section icon={<ShieldCheck />} title={t('leadership.applications.internal')}>{application.messages.filter(item => item.audience === 'reviewers').map(item => <Message key={item.id} item={item} />)}<MessageForm onSubmit={(body) => action(() => leadershipApi.message(application.id, { audience: 'reviewers', message_type: 'internal_comment', body }, guildKey))} /></Section>}
    {application.interview && <Section icon={<Clock3 />} title={t('leadership.applications.interview')}><p>{new Date(application.interview.scheduled_at).toLocaleString()} · {application.interview.timezone}</p><p className="text-sm text-slate-400">{application.interview.meeting_location}</p></Section>}
    {reviewer && application.vote_summary && <Section icon={<Vote />} title={t('leadership.applications.voting')}><div className="grid grid-cols-3 gap-2">{(['support','neutral','oppose'] as const).map(vote => <button key={vote} disabled={busy} onClick={() => void action(() => leadershipApi.vote(application.id, vote, undefined, guildKey))} className="min-h-11 rounded-lg border border-slate-700"><strong className="block">{application.vote_summary?.[vote] ?? 0}</strong>{t(`leadership.votes.${vote}`)}</button>)}</div><p className="mt-2 text-xs text-slate-500">{t('leadership.votes.participation', { count: application.vote_participation || 0 })}</p></Section>}
    {application.status === 'accepted' && <section className="rounded-xl border border-emerald-700 bg-emerald-950/20 p-4"><CheckCircle2 className="h-5 w-5 text-emerald-400" /><p className="mt-2 text-sm">{t('leadership.applications.acceptedNotice')}</p></section>}
    <div className="sticky bottom-2 z-10 grid gap-2 rounded-xl border border-slate-700 bg-slate-900/95 p-3 shadow-xl sm:flex">
      {!reviewer && activeStatuses.includes(application.status) && <button disabled={busy} onClick={() => void action(() => leadershipApi.withdraw(application.id))} className="min-h-11 rounded-lg border border-red-800 px-4 text-red-200">{t('leadership.applications.withdraw')}</button>}
      {summary.capabilities.manage && application.status === 'applied' && <ActionButton label={t('leadership.actions.startReview')} onClick={() => action(() => leadershipApi.status(application.id, 'under_review', undefined, guildKey))} />}
      {summary.capabilities.manage && activeStatuses.includes(application.status) && <><ActionButton label={t('leadership.actions.accept')} onClick={() => action(() => leadershipApi.decision(application.id, 'accepted', undefined, guildKey))} /><ActionButton label={t('leadership.actions.reject')} onClick={() => { const reason = window.prompt(t('leadership.fields.reason')); return reason ? action(() => leadershipApi.decision(application.id, 'rejected', reason, guildKey)) : Promise.resolve(); }} /></>}
    </div>
  </div>;
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) { return <section className="space-y-3 rounded-xl border border-slate-800 p-4"><h2 className="flex items-center gap-2 font-semibold">{icon}{title}</h2>{children}</section>; }
function Message({ item }: { item: LeadershipApplication['messages'][number] }) { return <div className="rounded-lg bg-slate-950 p-3"><div className="flex justify-between gap-2 text-xs text-slate-500"><span>{item.author_name}</span><time>{new Date(item.created_at).toLocaleString()}</time></div><p className="mt-1 whitespace-pre-wrap text-sm">{item.body}</p></div>; }
function MessageForm({ onSubmit, applicant = false }: { onSubmit: (body: string) => Promise<unknown>; applicant?: boolean }) { const { t } = useTranslation(); const [body,setBody]=useState(''); const submit=async(event:FormEvent)=>{event.preventDefault();if(!body.trim())return;await onSubmit(body.trim());setBody('');}; return <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row"><label className="sr-only" htmlFor={applicant ? 'applicant-message' : 'review-message'}>{t('leadership.fields.message')}</label><textarea id={applicant ? 'applicant-message' : 'review-message'} value={body} onChange={event=>setBody(event.target.value)} required minLength={2} maxLength={5000} className="min-h-24 flex-1 rounded-lg bg-slate-950 p-3" /><button className="min-h-11 rounded-lg bg-amber-500 px-4 font-semibold text-slate-950">{t('leadership.actions.send')}</button></form>; }
function ActionButton({ label, onClick }: { label: string; onClick: () => Promise<unknown> }) { return <button onClick={() => void onClick()} className="min-h-11 rounded-lg bg-amber-500 px-4 font-semibold text-slate-950">{label}</button>; }
