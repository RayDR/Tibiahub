import { AlertTriangle, CheckCircle2, LifeBuoy, Loader2, Shield } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, EmptyState, PageHeader } from '../../components/ui';
import { GuildDirectoryEntry, workspaceApi } from '../../services/workspaces';

export default function AssistanceHub() {
  const { t } = useTranslation();
  const [guilds, setGuilds] = useState<GuildDirectoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => { void workspaceApi.guilds().then(setGuilds).catch(() => setError(true)).finally(() => setLoading(false)); }, []);
  const attention = useMemo(() => guilds.filter(guild => guild.setup_status === 'needs_attention' || guild.open_alerts > 0), [guilds]);

  return <div className="space-y-5">
    <PageHeader size="md" title={t('workspace.assistanceHub.title')} subtitle={t('workspace.assistanceHub.subtitle')} iconElement={<LifeBuoy className="size-6" />} primaryAction={<Link to="/admin/guilds"><AppButton variant="secondary">{t('workspace.assistanceHub.allGuilds')}</AppButton></Link>} />
    {loading ? <div className="grid place-items-center py-12" role="status"><Loader2 className="size-7 animate-spin text-primary" /><span className="sr-only">{t('workspace.common.loading')}</span></div> : error ? <EmptyState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} /> : attention.length === 0 ? <EmptyState icon={<CheckCircle2 />} title={t('workspace.assistanceHub.clear')} description={t('workspace.assistanceHub.clearHelp')} /> : <div className="grid gap-3 md:grid-cols-2">
      {attention.map(guild => <Card key={guild.key} className="p-4"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{guild.name}</h2><p className="text-sm text-content-muted">{guild.world_name || t('workspace.common.unknownServer')}</p></div><Badge tone={guild.open_alerts ? 'warning' : 'primary'}>{guild.open_alerts ? t('workspace.assistanceHub.alerts', { count: guild.open_alerts }) : t('workspace.setup.needs_attention')}</Badge></div><div className="mt-4 flex items-center gap-2 text-sm text-content-secondary"><AlertTriangle className="size-4 text-warning" />{t('workspace.assistanceHub.review')}</div><Link to={`/admin/guilds/${guild.key}`} className="app-button-primary mt-4 w-full"><Shield className="size-4" />{t('workspace.assistanceHub.open')}</Link></Card>)}
    </div>}
  </div>;
}
