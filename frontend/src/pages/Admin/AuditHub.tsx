import { ClipboardList, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Card, EmptyState, PageHeader } from '../../components/ui';
import { GuildDirectoryEntry, workspaceApi } from '../../services/workspaces';

export default function AuditHub() {
  const { t } = useTranslation();
  const [guilds, setGuilds] = useState<GuildDirectoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => { void workspaceApi.guilds().then(setGuilds).catch(() => setError(true)).finally(() => setLoading(false)); }, []);
  return <div className="space-y-5">
    <PageHeader size="md" title={t('workspace.audits.title')} subtitle={t('workspace.audits.subtitle')} iconElement={<ClipboardList className="size-6" />} />
    {loading ? <div className="grid place-items-center py-12" role="status"><Loader2 className="size-7 animate-spin text-primary" /><span className="sr-only">{t('workspace.common.loading')}</span></div> : error ? <EmptyState title={t('workspace.audits.error')} description={t('workspace.errors.tryAgain')} /> : guilds.length === 0 ? <EmptyState title={t('workspace.audits.empty')} description={t('workspace.audits.emptyHelp')} /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{guilds.map(guild => <Card key={guild.key} className="p-4"><h2 className="font-semibold">{guild.name}</h2><p className="mt-1 text-sm text-content-muted">{t('workspace.audits.guildHelp')}</p><Link to={`/admin/guilds/${guild.key}#audit`} className="app-button-secondary mt-4 w-full">{t('workspace.audits.open')}</Link></Card>)}</div>}
  </div>;
}
