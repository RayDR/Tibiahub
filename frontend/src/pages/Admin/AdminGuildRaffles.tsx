import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { EmptyState } from '../../components/workspace/WorkspacePrimitives';
import RafflesWorkspace from '../guild/RafflesWorkspace';
import { AdminGuildWorkspace, workspaceApi } from '../../services/workspaces';

export default function AdminGuildRaffles() {
  const { t } = useTranslation(); const { guildKey = '' } = useParams(); const [data, setData] = useState<AdminGuildWorkspace | null>(null); const [error, setError] = useState(false);
  useEffect(() => { void workspaceApi.adminGuild(guildKey).then(setData).catch(() => setError(true)); }, [guildKey]);
  if (error) return <EmptyState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} />;
  if (!data) return <div className="p-8 text-center text-content-secondary">{t('workspace.common.loading')}</div>;
  return <RafflesWorkspace guildName={data.guild.name} worldName={data.guild.world_name} assistance />;
}
