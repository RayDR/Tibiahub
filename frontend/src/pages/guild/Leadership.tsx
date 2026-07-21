import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ClipboardList, ShieldCheck, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import { LeadershipSummary, leadershipApi } from '../../services/leadership';

export default function Leadership({ guildKey, guildName }: { guildKey?: string; guildName?: string }) {
  const { t } = useTranslation(); const [data, setData] = useState<LeadershipSummary | null>(null); const [error, setError] = useState(false);
  useEffect(() => { void leadershipApi.summary(guildKey).then(setData).catch(() => setError(true)); }, [guildKey]);
  if (error) return <EmptyState title={t('leadership.errors.load')} description={t('leadership.errors.retry')} />;
  if (!data) return <div className="grid gap-3 sm:grid-cols-2">{[0,1,2,3].map(value => <div key={value} className="h-28 animate-pulse rounded-xl bg-slate-900" />)}</div>;
  const cards = [['active', data.active_viceleaders, ShieldCheck], ['positions', data.open_positions, Users], ['interviews', data.interviews_pending, ClipboardList], ['accepted', data.recently_accepted, CheckCircle2]] as const;
  return <div className="space-y-4"><WorkspaceHeader title={t('leadership.title')} subtitle={guildName || data.guild_name} badge={t('leadership.roles.viceleader')} action={<Link to={guildKey ? `/admin/guilds/${guildKey}/leadership/recruitment` : '/guild/leadership/recruitment'} className="inline-flex min-h-11 items-center rounded-lg bg-amber-500 px-4 font-semibold text-slate-950">{t('leadership.recruitment.open')}</Link>} />
    {data.below_recommended && <section className="flex gap-3 rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100"><AlertTriangle className="h-5 w-5 shrink-0" /><div><strong>{t('leadership.warning.title')}</strong><p className="mt-1 text-amber-100/80">{t('leadership.warning.belowMinimum')}</p></div></section>}
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{cards.map(([key, value, Icon]) => <article key={key} className="rounded-xl border border-slate-800 p-4"><Icon className="h-5 w-5 text-amber-400" /><strong className="mt-3 block text-2xl">{value}</strong><span className="text-xs text-slate-400">{t(`leadership.summary.${key}`)}</span></article>)}</div>
    <section className="rounded-xl border border-slate-800 p-4"><h2 className="font-semibold">{t('leadership.assignment.manualTitle')}</h2><p className="mt-2 text-sm text-slate-400">{t('leadership.assignment.manualNotice')}</p></section>
  </div>;
}
