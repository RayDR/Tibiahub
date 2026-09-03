import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownAZ, ExternalLink, Loader2, Mail, RefreshCcw, Search, Users, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { AppButton, Badge, Card, DataRegion, DegradedState, EmptyState, ErrorState, Input, LoadingState, PaginationControls, Table, TableContainer } from '../../components/ui';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { useAuth } from '../../context/AuthContext';
import { GuildMember, guildApi } from '../../services/guild';
import { useGuildContext } from '../../utils/guildContext';
import { useGuildCapability } from '../../hooks/useGuildCapability';
import { formatDateTime } from '../../utils/locale';

const PAGE_SIZE = 12;

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
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'level' | 'name'>('level');
  const [selectedMember, setSelectedMember] = useState<GuildMember | null>(null);
  const canSync = canManageGuild(guildName);
  const requestRef = useRef<AbortController | null>(null);
  const retrySkipRef = useRef(0);

  const load = useCallback(async (nextSkip = 0, force = false) => {
    if (!guildName) return;
    requestRef.current?.abort();
    retrySkipRef.current = nextSkip;
    const controller = new AbortController();
    requestRef.current = controller;
    force ? setBusySync(true) : setLoading(true);
    setError(false);
    const params = { skip: nextSkip, limit: PAGE_SIZE, search: query.trim() || undefined, sort };
    try {
      const payload = force
        ? await guildApi.syncGuildMembers(guildName, params)
        : await guildApi.getGuildMembers(guildName, params, controller.signal);
      if (controller.signal.aborted) return;
      setMembers(payload.members);
      setTotal(payload.total);
      setSkip(payload.skip);
      setSource(payload.source);
      setSelectedMember(null);
    } catch (loadError: any) {
      if (loadError?.name !== 'CanceledError' && loadError?.code !== 'ERR_CANCELED') setError(true);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
        setBusySync(false);
      }
    }
  }, [guildName, query, sort]);
  useEffect(() => {
    setMembers([]);
    setTotal(0);
    setSkip(0);
  }, [guildName]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(0), 200);
    return () => { window.clearTimeout(timer); requestRef.current?.abort(); };
  }, [load]);

  if (loading && members.length === 0) return <LoadingState title={t('guildMembers.loading')} />;
  return <div className="workspace-page">
    <WorkspaceContentHeader title={t('guildMembers.title')} description={t('guildMembers.subtitle', { guild: guildName })} icon={<Users />} action={<><Badge tone={source === 'live' ? 'success' : 'neutral'}>{t(`guildMembers.sources.${source}`)}</Badge>{canSync ? <AppButton onClick={() => void load(0, true)} disabled={busySync}>{busySync ? <Loader2 className="size-4 animate-spin" /> : <RefreshCcw className="size-4" />}{t('guildMembers.refresh')}</AppButton> : null}</>} />
    {error && members.length === 0 ? <ErrorState title={t('guildMembers.error')} description={t('guildMembers.errorHelp')} action={<AppButton onClick={() => void load(0)}>{t('common.retry')}</AppButton>} /> : <>
      {error ? <DegradedState title={t('guildMembers.error')} description={t('guildMembers.errorHelp')} action={<AppButton onClick={() => void load(retrySkipRef.current)}>{t('common.retry')}</AppButton>} /> : null}
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><label className="relative"><span className="sr-only">{t('guildMembers.search')}</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" /><Input className="pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('guildMembers.searchPlaceholder')} /></label><AppButton variant="secondary" onClick={() => setSort(value => value === 'level' ? 'name' : 'level')}><ArrowDownAZ className="size-4" />{t(`guildMembers.sort.${sort}`)}</AppButton></div>
      {selectedMember ? <MemberDetail member={selectedMember} onClose={() => setSelectedMember(null)} /> : null}
      {members.length === 0 ? <EmptyState title={query ? t('guildMembers.noMatches') : t('guildMembers.empty')} description={query ? t('guildMembers.noMatchesHelp') : t('guildMembers.emptyHelp')} /> : <>
        <div className="responsive-card-list">{members.map(member => <MemberCard key={`${member.character_name}-${member.snapshot_at}`} member={member} onSelect={() => setSelectedMember(member)} />)}</div>
        <DataRegion className="responsive-data-table" aria-label={t('guildMembers.title')} aria-busy={loading}><TableContainer><Table><thead><tr><th>{t('guildMembers.fields.character')}</th><th>{t('guildMembers.fields.level')}</th><th>{t('guildMembers.fields.vocation')}</th><th>{t('guildMembers.fields.rank')}</th><th>{t('identity.accountStatus')}</th><th>{t('guildMembers.fields.lastLogin')}</th></tr></thead><tbody>{members.map(member => <tr key={`${member.character_name}-${member.snapshot_at}`}><td className="font-medium text-content-primary"><button type="button" className="text-left text-primary hover:underline" onClick={() => setSelectedMember(member)}>{member.character_name}</button></td><td>{member.level ?? t('common.notAvailable')}</td><td>{member.vocation || t('common.unknown')}</td><td>{member.rank || member.role || t('guildMembers.values.member')}</td><td><Badge tone={member.linked_username ? 'success' : 'neutral'}>{t(member.linked_username ? 'identity.registered' : 'identity.unregistered')}</Badge></td><td className="text-sm text-content-muted">{member.last_login || t('common.unknown')}</td></tr>)}</tbody></Table></TableContainer></DataRegion>
        <PaginationControls skip={skip} limit={PAGE_SIZE} total={total} loading={loading} onPrevious={() => void load(Math.max(0, skip - PAGE_SIZE))} onNext={() => void load(skip + PAGE_SIZE)} />
      </>}
    </>}
  </div>;
}

function MemberCard({ member, onSelect }: { member: GuildMember; onSelect: () => void }) {
  const { t } = useTranslation();
  return <Card className="p-4"><button type="button" onClick={onSelect} className="w-full text-left"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold text-primary hover:underline">{member.character_name}</h2><p className="text-sm text-content-muted">{member.vocation || t('common.unknown')}</p></div><Badge tone="primary">{t('guildMembers.levelValue', { level: member.level ?? t('common.notAvailable') })}</Badge></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-content-muted">{t('guildMembers.fields.rank')}</dt><dd>{member.rank || member.role || t('guildMembers.values.member')}</dd></div><div><dt className="text-xs text-content-muted">{t('identity.accountStatus')}</dt><dd>{t(member.linked_username ? 'identity.registered' : 'identity.unregistered')}</dd></div></dl></button></Card>;
}

function MemberDetail({ member, onClose }: { member: GuildMember; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const fields: Array<[string, string | number | undefined]> = [
    [t('guildMembers.fields.level'), member.level], [t('guildMembers.fields.vocation'), member.vocation],
    [t('guildMembers.fields.rank'), member.rank], [t('guildMembers.detail.role'), member.role], [t('guildMembers.detail.world'), member.world],
    [t('guildMembers.fields.lastLogin'), member.last_login], [t('guildMembers.detail.snapshot'), formatDateTime(member.snapshot_at, i18n.resolvedLanguage || i18n.language)],
    [t('guildMembers.detail.username'), member.linked_username],
  ];
  return <Card className="border-primary/25 p-5" role="region" aria-label={`${member.character_name} details`}><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-primary">{t('guildMembers.detail.title')}</p><h2 className="text-xl font-bold text-content-primary">{member.character_name}</h2></div><button type="button" onClick={onClose} className="grid size-9 place-items-center rounded-lg border border-line" aria-label={t('guildMembers.detail.close')}><X className="size-4" /></button></div><dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{fields.filter(([, value]) => value != null && value !== '').map(([label, value]) => <div key={label} className="rounded-lg border border-line bg-surface-base/50 p-3"><dt className="text-xs text-content-muted">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-content-primary">{value}</dd></div>)}</dl><div className="mt-4 flex flex-wrap gap-2">{member.linked_email ? <a href={`mailto:${member.linked_email}`} className="app-button-secondary app-button-sm"><Mail className="size-4" />{member.linked_email}</a> : null}{member.linked_username ? <Link to={`/members/${encodeURIComponent(member.linked_username)}`} className="app-button-primary app-button-sm"><ExternalLink className="size-4" />{t('guildMembers.detail.openProfile')}</Link> : <Badge tone="neutral">{t('identity.unregistered')}</Badge>}</div></Card>;
}
