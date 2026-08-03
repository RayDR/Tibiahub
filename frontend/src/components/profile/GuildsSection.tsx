import { Castle, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, Card, EmptyState } from '../ui';
import { ProfileIdentity } from '../../services/profile';

export default function GuildsSection({ profile }: { profile: ProfileIdentity }) {
  const { t } = useTranslation();
  if (!profile.guild_contexts.length) return <EmptyState title={t('identity.noGuilds')} description={t('identity.noGuildsHelp')} />;
  return <div className="grid gap-4 lg:grid-cols-2">{profile.guild_contexts.map(row => <Card key={`${row.guild_name}-${row.world_name}`} className="p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><Castle className="size-5 text-primary" />{row.guild_name}</h2><p className="text-sm text-content-muted">{row.world_name || '—'} · {row.representative_character_name || '—'}</p></div><Badge tone="primary">{t(`identity.roles.${row.role}`, { defaultValue: row.role })}</Badge></div><div className="mt-4 flex flex-wrap gap-2">{Object.entries(row.capabilities).filter(([, enabled]) => enabled).map(([name]) => <Badge key={name}>{t(`identity.capabilities.${name}`)}</Badge>)}</div><Link to="/guild" className="app-button-primary mt-4"><ExternalLink className="size-4" />{t('identity.openGuild')}</Link></Card>)}</div>;
}
