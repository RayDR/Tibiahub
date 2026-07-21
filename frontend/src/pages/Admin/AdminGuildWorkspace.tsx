import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AssistanceBanner, EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import { AdminGuildWorkspace as Workspace, workspaceApi } from '../../services/workspaces';

export default function AdminGuildWorkspace() {
  const { t } = useTranslation();
  const { guildKey = '' } = useParams();
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { void workspaceApi.adminGuild(guildKey).then(setData).catch(() => setError(true)); }, [guildKey]);
  if (error) return <EmptyState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} />;
  if (!data) return <div className="p-8 text-center text-slate-400">{t('workspace.common.loading')}</div>;
  const guild = data.guild;
  const cards = [['members', guild.member_count], ['leader', guild.leader || '—'], ['setup', t(`workspace.setup.${guild.setup_status}`)], ['alerts', guild.open_alerts]];
  return <div className="space-y-4">
    <AssistanceBanner guildName={guild.name} />
    <WorkspaceHeader title={guild.name} subtitle={guild.world_name || t('workspace.common.unknownServer')} badge={t('workspace.assistance.badge')} />
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{cards.map(([key, value]) => <div key={String(key)} className="rounded-xl border border-slate-800 p-4"><p className="text-xs uppercase text-slate-500">{t(`workspace.common.${key}`)}</p><strong className="mt-1 block">{value}</strong></div>)}</div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Link to={`/admin/management?guild=${encodeURIComponent(guild.name)}`} className="flex min-h-11 items-center justify-center rounded-lg bg-sky-600 px-4 py-2 text-white">{t('workspace.assistance.manage')}</Link>
      <Link to={`/admin/guilds/${guild.key}/raffles`} className="flex min-h-11 items-center justify-center rounded-lg border border-sky-700 px-4 py-2 text-sky-200">{t('raffle.workspace.manageRaffles')}</Link>
      <Link to={`/admin/guilds/${guild.key}/leadership`} className="flex min-h-11 items-center justify-center rounded-lg border border-amber-700 px-4 py-2 text-amber-200">{t('leadership.navigation')}</Link>
      <Link to="/guild" className="flex min-h-11 items-center justify-center rounded-lg border border-slate-700 px-4 py-2">{t('workspace.assistance.publicView')}</Link>
    </div>
  </div>;
}
