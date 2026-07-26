import { ClipboardList, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Badge, Card, EmptyState, LoadingState, PageHeader } from '../../components/ui';
import { AdminGuildWorkspace as Workspace, WorkspaceAuditEntry, workspaceApi } from '../../services/workspaces';

export default function AdminGuildWorkspace() {
  const { t } = useTranslation();
  const { guildKey = '' } = useParams();
  const [data, setData] = useState<Workspace | null>(null);
  const [audits, setAudits] = useState<WorkspaceAuditEntry[]>([]);
  const [loadingAudits, setLoadingAudits] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    setError(false);
    void Promise.all([workspaceApi.adminGuild(guildKey), workspaceApi.guildAudits(guildKey)])
      .then(([workspace, rows]) => { setData(workspace); setAudits(rows); })
      .catch(() => setError(true))
      .finally(() => setLoadingAudits(false));
  }, [guildKey]);
  if (error) return <EmptyState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} />;
  if (!data) return <LoadingState title={t('workspace.common.loading')} />;
  const guild = data.guild;
  const cards = [['members', guild.member_count], ['leader', guild.leader || '—'], ['setup', t(`workspace.setup.${guild.setup_status}`)], ['alerts', guild.open_alerts]];
  return <div className="space-y-5">
    <PageHeader size="md" title={guild.name} subtitle={guild.world_name || t('workspace.common.unknownServer')} eyebrow={t('workspace.assistance.badge')} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([key, value]) => <Card key={String(key)} className="p-4"><p className="text-xs uppercase text-content-muted">{t(`workspace.common.${key}`)}</p><strong className="mt-1 block text-xl">{value}</strong></Card>)}</div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Link to={`/admin/management?guild=${encodeURIComponent(guild.name)}`} className="app-button-primary">{t('workspace.assistance.manage')}</Link>
      <Link to={`/admin/guilds/${guild.key}/raffles`} className="app-button-secondary">{t('raffle.workspace.manageRaffles')}</Link>
      <Link to={`/admin/guilds/${guild.key}/leadership`} className="app-button-secondary">{t('leadership.navigation')}</Link>
      <Link to="/guild" className="app-button-secondary">{t('workspace.assistance.publicView')}</Link>
    </div>
    <section id="audit" className="scroll-mt-28 rounded-xl border border-line p-4"><div className="mb-3 flex items-center gap-2"><ClipboardList className="size-5 text-primary" /><h2 className="font-semibold">{t('workspace.audits.recent')}</h2></div>{loadingAudits ? <Loader2 className="size-5 animate-spin text-primary" /> : audits.length === 0 ? <p className="text-sm text-content-muted">{t('workspace.audits.noEntries')}</p> : <div className="space-y-2">{audits.slice(0, 20).map(row => <div key={row.id} className="flex flex-col gap-1 rounded-lg bg-surface-raised p-3 text-sm sm:flex-row sm:items-center sm:justify-between"><div><strong>{row.action}</strong>{row.target_type ? <p className="text-xs text-content-muted">{row.target_type}</p> : null}</div><Badge>{new Date(row.created_at).toLocaleString()}</Badge></div>)}</div>}</section>
  </div>;
}
