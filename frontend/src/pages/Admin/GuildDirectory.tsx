import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Shield, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import { GuildDirectoryEntry, workspaceApi } from '../../services/workspaces';

export default function GuildDirectory() {
  const { t } = useTranslation();
  const [guilds, setGuilds] = useState<GuildDirectoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => { void workspaceApi.guilds().then(setGuilds).catch(() => setError(true)).finally(() => setLoading(false)); }, []);
  return <div className="space-y-4"><WorkspaceHeader title={t('workspace.adminGuilds.title')} subtitle={t('workspace.adminGuilds.subtitle')} badge={t('workspace.admin.badge')} />{loading ? <div className="flex justify-center p-12"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div> : error ? <EmptyState title={t('workspace.errors.guildDirectory')} description={t('workspace.errors.tryAgain')} /> : guilds.length === 0 ? <EmptyState title={t('workspace.adminGuilds.empty')} description={t('workspace.adminGuilds.emptyHelp')} /> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{guilds.map(guild => <article key={guild.key} className="admin-panel rounded-xl p-4"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{guild.name}</h2><p className="text-sm text-content-muted">{guild.world_name || t('workspace.common.unknownServer')}</p></div><Shield className="h-5 w-5 text-primary" /></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-content-muted">{t('workspace.common.leader')}</dt><dd>{guild.leader || '—'}</dd></div><div><dt className="text-content-muted">{t('workspace.common.members')}</dt><dd className="flex items-center gap-1"><Users className="h-4 w-4" />{guild.member_count}</dd></div><div><dt className="text-content-muted">{t('workspace.common.setup')}</dt><dd>{t(`workspace.setup.${guild.setup_status}`)}</dd></div><div><dt className="text-content-muted">{t('workspace.common.alerts')}</dt><dd>{guild.open_alerts}</dd></div></dl><Link to={`/admin/guilds/${guild.key}`} className="admin-primary mt-4 flex min-h-11 w-full items-center justify-center rounded-lg px-4 py-2 font-medium">{t('workspace.adminGuilds.open')}</Link></article>)}</div>}</div>;
}
