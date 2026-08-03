import { useEffect, useMemo, useState } from 'react';
import { ArrowDownAZ, Loader2, RefreshCcw, Search, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, EmptyState, Input, LoadingState, PageHeader, Table, TableContainer } from '../../components/ui';
import { useAuth } from '../../context/AuthContext';
import { GuildMember, guildApi } from '../../services/guild';
import { useGuildContext } from '../../utils/guildContext';
import { useGuildCapability } from '../../hooks/useGuildCapability';

export default function GuildMembersPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const guildName = useGuildContext(user);
  const { canManageGuild } = useGuildCapability('announcements.manage');
  const [members, setMembers] = useState<GuildMember[]>([]);
  const [source, setSource] = useState<'live' | 'snapshot'>('snapshot');
  const [loading, setLoading] = useState(true);
  const [busySync, setBusySync] = useState(false);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'level' | 'name'>('level');
  const canSync = canManageGuild(guildName);

  const load = async (force = false) => {
    if (!guildName) return;
    force ? setBusySync(true) : setLoading(true); setError(false);
    try { const payload = force ? await guildApi.syncGuildMembers(guildName) : await guildApi.getGuildMembers(guildName); setMembers(payload.members); setSource(payload.source); }
    catch { setError(true); }
    finally { setLoading(false); setBusySync(false); }
  };
  useEffect(() => { void load(); }, [guildName]);
  const visible = useMemo(() => members.filter(member => `${member.character_name} ${member.vocation || ''} ${member.rank || member.role || ''}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())).sort((a, b) => sort === 'level' ? (b.level || 0) - (a.level || 0) : a.character_name.localeCompare(b.character_name)), [members, query, sort]);

  if (loading) return <LoadingState title={t('guildMembers.loading')} />;
  return <div className="space-y-5">
    <PageHeader size="md" title={t('guildMembers.title')} subtitle={t('guildMembers.subtitle', { guild: guildName })} iconElement={<Users className="size-6" />} primaryAction={canSync ? <AppButton onClick={() => void load(true)} disabled={busySync}>{busySync ? <Loader2 className="size-4 animate-spin" /> : <RefreshCcw className="size-4" />}{t('guildMembers.refresh')}</AppButton> : undefined} secondaryActions={<Badge tone={source === 'live' ? 'success' : 'neutral'}>{t(`guildMembers.sources.${source}`)}</Badge>} />
    {error ? <EmptyState title={t('guildMembers.error')} description={t('guildMembers.errorHelp')} action={<AppButton onClick={() => void load()}>{t('common.retry')}</AppButton>} /> : <>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><label className="relative"><span className="sr-only">{t('guildMembers.search')}</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><Input className="pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('guildMembers.searchPlaceholder')} /></label><AppButton variant="secondary" onClick={() => setSort(value => value === 'level' ? 'name' : 'level')}><ArrowDownAZ className="size-4" />{t(`guildMembers.sort.${sort}`)}</AppButton></div>
      {visible.length === 0 ? <EmptyState title={query ? t('guildMembers.noMatches') : t('guildMembers.empty')} description={query ? t('guildMembers.noMatchesHelp') : t('guildMembers.emptyHelp')} /> : <>
        <div className="responsive-card-list">{visible.map(member => <MemberCard key={`${member.character_name}-${member.snapshot_at}`} member={member} />)}</div>
        <TableContainer className="responsive-data-table"><Table><thead><tr><th>{t('guildMembers.fields.character')}</th><th>{t('guildMembers.fields.level')}</th><th>{t('guildMembers.fields.vocation')}</th><th>{t('guildMembers.fields.rank')}</th><th>{t('guildMembers.fields.lastLogin')}</th></tr></thead><tbody>{visible.map(member => <tr key={`${member.character_name}-${member.snapshot_at}`}><td className="font-medium text-content-primary">{member.character_name}</td><td>{member.level ?? t('common.notAvailable')}</td><td>{member.vocation || t('common.unknown')}</td><td>{member.rank || member.role || t('guildMembers.values.member')}</td><td className="text-sm text-content-muted">{member.last_login || t('common.unknown')}</td></tr>)}</tbody></Table></TableContainer>
      </>}
    </>}
  </div>;
}

function MemberCard({ member }: { member: GuildMember }) {
  const { t } = useTranslation();
  return <Card className="p-4"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{member.character_name}</h2><p className="text-sm text-content-muted">{member.vocation || t('common.unknown')}</p></div><Badge tone="primary">{t('guildMembers.levelValue', { level: member.level ?? t('common.notAvailable') })}</Badge></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-content-muted">{t('guildMembers.fields.rank')}</dt><dd>{member.rank || member.role || t('guildMembers.values.member')}</dd></div><div><dt className="text-xs text-content-muted">{t('guildMembers.fields.lastLogin')}</dt><dd>{member.last_login || t('common.unknown')}</dd></div></dl></Card>;
}
