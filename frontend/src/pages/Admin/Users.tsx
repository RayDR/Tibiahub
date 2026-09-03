import axios from 'axios';
import { useEffect, useRef, useState } from 'react';
import { KeyRound, Loader2, MessagesSquare, PenLine, Save, Shield, ShieldOff, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { DataRegion, DegradedState, EmptyState, ErrorState, Table, TableContainer } from '../../components/ui';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import {
  guildManagementApi,
  GuildManagementGrant,
  GuildMember,
} from '../../services/guildManagement';
import AdminIdentityLinker from '../../components/admin/AdminIdentityLinker';
import { adminEmailApi } from '../../services/adminEmail';
import { boundedWindow } from '../../utils/pagination';
import { supportedLanguage } from '../../utils/locale';

const SUPPORTED_CAPABILITY_COUNT = 4;
const PAGE_SIZE = 10;

function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return fallback;
}

export default function AdminUsers() {
  const { t, i18n } = useTranslation();
  const { success: showSuccess, error: showError } = useToast();
  const confirmation = useConfirmation();
  const [users, setUsers] = useState<GuildMember[]>([]);
  const [guilds, setGuilds] = useState<string[]>([]);
  const [selectedGuild, setSelectedGuild] = useState('');
  const [grants, setGrants] = useState<GuildManagementGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingGrants, setLoadingGrants] = useState(false);
  const [saving, setSaving] = useState<number | null>(null);
  const [grantSaving, setGrantSaving] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [additionalError, setAdditionalError] = useState(false);
  const [skip, setSkip] = useState(0);
  const requestInFlight = useRef(false);
  const retrySkipRef = useRef(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      guildManagementApi.getUsers(0, PAGE_SIZE + 1, { include_inactive: true, exclude_test_accounts: false }),
      guildManagementApi.getManageableGuilds(),
    ])
      .then(([loadedUsers, context]) => {
        if (!active) return;
        const window = boundedWindow(loadedUsers, PAGE_SIZE);
        setUsers(window.items);
        setSkip(0);
        setHasMore(window.hasMore);
        setGuilds(context.guilds);
        setSelectedGuild(context.guilds[0] || '');
      })
      .catch(() => active && setError(true))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const loadWindow = async (nextSkip: number) => {
    if (requestInFlight.current || loadingMore || nextSkip < 0) return;
    requestInFlight.current = true;
    retrySkipRef.current = nextSkip;
    setLoadingMore(true);
    setAdditionalError(false);
    try {
      const rows = await guildManagementApi.getUsers(nextSkip, PAGE_SIZE + 1, { include_inactive: true, exclude_test_accounts: false });
      const page = boundedWindow(rows, PAGE_SIZE);
      setUsers(page.items);
      setSkip(nextSkip);
      setHasMore(page.hasMore);
    } catch {
      setAdditionalError(true);
      showError(t('workspace.errors.tryAgain'));
    } finally {
      setLoadingMore(false);
      requestInFlight.current = false;
    }
  };

  useEffect(() => {
    if (!selectedGuild) {
      setGrants([]);
      return;
    }
    let active = true;
    setLoadingGrants(true);
    guildManagementApi.getGuildPermissions(selectedGuild)
      .then(rows => active && setGrants(rows))
      .catch(error => {
        if (active) showError(apiErrorMessage(error, t('workspace.adminUsers.grantsLoadFailed')));
      })
      .finally(() => active && setLoadingGrants(false));
    return () => { active = false; };
  }, [selectedGuild, t, showError]);

  const update = async (user: GuildMember, patch: Partial<GuildMember>) => {
    setSaving(user.id);
    try {
      const saved = await guildManagementApi.updateUser(user.id, patch);
      setUsers(items => items.map(item => item.id === saved.id ? saved : item));
      showSuccess(t('workspace.users.saved'));
    } catch {
      showError(t('workspace.users.saveFailed'));
    } finally {
      setSaving(null);
    }
  };

  const grantAll = async (user: GuildMember) => {
    if (!selectedGuild) return;
    setGrantSaving(user.id);
    try {
      const rows = await guildManagementApi.grantAllGuildPermissions(selectedGuild, user.id);
      setGrants(current => [
        ...current.filter(row => row.user_id !== user.id),
        ...rows,
      ]);
      showSuccess(t('workspace.adminUsers.grantSuccess', { user: user.display_name || user.username, guild: selectedGuild }));
    } catch (error) {
      showError(apiErrorMessage(error, t('workspace.adminUsers.grantFailed')));
    } finally {
      setGrantSaving(null);
    }
  };

  const revokeAll = async (user: GuildMember) => {
    if (!selectedGuild) return;
    const confirmed = await confirmation.confirm(
      t('workspace.adminUsers.revokeConfirm', { user: user.display_name || user.username, guild: selectedGuild }),
      { title: t('workspace.adminUsers.revokeAll'), confirmLabel: t('workspace.adminUsers.revokeAll'), danger: true },
    );
    if (!confirmed) return;
    setGrantSaving(user.id);
    try {
      const result = await guildManagementApi.revokeAllGuildPermissions(selectedGuild, user.id);
      setGrants(current => current.filter(row => row.user_id !== user.id));
      showSuccess(t('workspace.adminUsers.revokeSuccess', { count: result.revoked }));
    } catch (error) {
      showError(apiErrorMessage(error, t('workspace.adminUsers.revokeFailed')));
    } finally {
      setGrantSaving(null);
    }
  };

  const queueAccountEmail = async (user: GuildMember, kind: 'verify'|'reset') => {
    setSaving(user.id);
    try {
      const locale = supportedLanguage(i18n.resolvedLanguage || i18n.language);
      if (kind === 'verify') await adminEmailApi.verify(user.id, locale);
      else await adminEmailApi.reset(user.id, locale);
      showSuccess(t(`identity.admin.${kind}Queued`));
    } catch { showError(t('identity.emailAdmin.error')); }
    finally { setSaving(null); }
  };

  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        title={t('workspace.adminUsers.title')}
        description={t('workspace.adminUsers.subtitle')}
        icon={<Users />}
      />
      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>
      ) : error ? (
        <ErrorState title={t('workspace.errors.users')} description={t('workspace.errors.tryAgain')} action={<button type="button" className="app-button-secondary" onClick={() => window.location.reload()}>{t('common.retry')}</button>} />
      ) : (
        <>
          <AdminIdentityLinker users={users} onLinked={(userId) => { void guildManagementApi.getUserDetail(userId).then(saved => setUsers(items => items.map(item => item.id === saved.id ? saved : item))); }} />
          <section className="admin-panel rounded-xl p-4" aria-labelledby="guild-permissions-title">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="guild-permissions-title" className="flex items-center gap-2 font-semibold">
                  <KeyRound className="h-4 w-4 text-primary" />
                  {t('workspace.adminUsers.guildPermissions')}
                </h2>
                <p className="mt-1 text-sm text-content-muted">{t('workspace.adminUsers.guildPermissionsHelp')}</p>
              </div>
              <label className="grid min-w-56 gap-1 text-sm">
                <span className="text-content-muted">{t('workspace.adminUsers.guild')}</span>
                <select
                  value={selectedGuild}
                  onChange={event => setSelectedGuild(event.target.value)}
                  className="admin-secondary min-h-11 rounded-lg bg-transparent px-3"
                >
                  {guilds.length === 0 && <option value="">{t('workspace.adminUsers.noGuilds')}</option>}
                  {guilds.map(guild => <option key={guild} value={guild}>{guild}</option>)}
                </select>
              </label>
            </div>
          </section>

          {users.length === 0 ? <EmptyState title={t('workspace.adminUsers.title')} description={t('workspace.adminUsers.subtitle')} /> : <>
          {additionalError ? <DegradedState title={t('workspace.errors.users')} description={t('workspace.errors.tryAgain')} action={<button type="button" className="app-button-secondary app-button-sm" onClick={() => void loadWindow(retrySkipRef.current)}>{t('common.retry')}</button>} /> : null}
          <div className="responsive-card-list">{users.map(user => {
            const userGrantCount = new Set(grants.filter(row => row.user_id === user.id).map(row => row.capability)).size;
            const hasGrants = userGrantCount > 0;
            const permissionBusy = loadingGrants || grantSaving === user.id || !selectedGuild;
            return <article key={user.id} className="rounded-xl border border-line bg-surface-base/50 p-4"><div className="flex items-start justify-between gap-3"><div><strong>{user.display_name || user.username}</strong><p className="break-all text-xs text-content-muted">{user.email || user.username}</p><p className="text-xs text-content-muted">{user.guild_name || t('workspace.common.noGuild')}</p></div><span className={`rounded-full px-2 py-1 text-xs ${user.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>{user.is_active ? t('workspace.users.active') : t('workspace.users.inactive')}</span></div><div className="mt-4 grid gap-2">{([['is_superuser', Shield, t('workspace.users.admin')], ['is_moderator', MessagesSquare, t('workspace.users.moderator')], ['is_writer', PenLine, t('workspace.users.writer')]] as const).map(([key, Icon, label]) => <label key={key} className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(user[key])} disabled={saving === user.id} onChange={event => void update(user, { [key]: event.target.checked })} /><Icon className="size-3.5 text-primary" /><span>{label}</span></label>)}</div><p className="mt-3 text-xs text-content-muted">{loadingGrants ? t('workspace.adminUsers.loadingGrants') : t('workspace.adminUsers.activeGrantCount', { count: userGrantCount, total: SUPPORTED_CAPABILITY_COUNT })}</p><div className="mt-2 flex flex-wrap gap-2"><button type="button" disabled={permissionBusy || !user.is_active || userGrantCount === SUPPORTED_CAPABILITY_COUNT} onClick={() => void grantAll(user)} className="app-button-primary app-button-sm">{grantSaving === user.id ? <Loader2 className="size-4 animate-spin" /> : <Shield className="size-4" />}{t('workspace.adminUsers.grantAll')}</button><button type="button" disabled={permissionBusy || !hasGrants} onClick={() => void revokeAll(user)} className="app-button-danger app-button-sm"><ShieldOff className="size-4" />{t('workspace.adminUsers.revokeAll')}</button>{user.email ? <><button type="button" className="app-button-secondary app-button-sm" disabled={saving === user.id} onClick={() => void queueAccountEmail(user, 'verify')}>{t('identity.admin.resendVerification')}</button><button type="button" className="app-button-secondary app-button-sm" disabled={saving === user.id} onClick={() => void queueAccountEmail(user, 'reset')}>{t('identity.admin.sendReset')}</button></> : null}</div></article>;
          })}</div>
          <DataRegion className="responsive-data-table" aria-label={t('workspace.adminUsers.title')} aria-busy={loadingMore}>
            <TableContainer>
            <Table className="min-w-[64rem] text-sm">
              <thead className="bg-surface-raised text-xs uppercase tracking-wide text-content-muted"><tr><th className="p-3">{t('workspace.adminUsers.columns.user')}</th><th className="p-3">{t('workspace.adminUsers.columns.status')}</th><th className="p-3">{t('workspace.adminUsers.columns.roles')}</th><th className="p-3">{t('workspace.adminUsers.columns.guildPermissions')}</th><th className="p-3">{t('workspace.adminUsers.columns.actions')}</th></tr></thead>
              <tbody className="divide-y divide-line">{users.map(user => {
                const userGrantCount = new Set(grants.filter(row => row.user_id === user.id).map(row => row.capability)).size;
                const hasGrants = userGrantCount > 0;
                const permissionBusy = loadingGrants || grantSaving === user.id || !selectedGuild;
                return <tr key={user.id} className="align-top hover:bg-surface-hover/40">
                  <td className="p-3"><div className="flex items-center gap-3"><div className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-full bg-surface-raised">{user.avatar_url ? <img src={user.avatar_url} alt="" className="size-full object-cover" /> : <Shield className="size-4 text-content-muted" />}</div><div><strong className="text-content-primary">{user.display_name || user.username}</strong><p className="text-xs text-content-muted">{user.email || user.username}</p><p className="text-xs text-content-muted">{user.guild_name || t('workspace.common.noGuild')}</p></div></div></td>
                  <td className="p-3"><span className={`rounded-full px-2 py-1 text-xs ${user.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>{user.is_active ? t('workspace.users.active') : t('workspace.users.inactive')}</span>{saving === user.id ? <Save className="ml-2 inline size-3 animate-pulse" /> : null}</td>
                  <td className="p-3"><div className="grid gap-1">{([['is_superuser', Shield, t('workspace.users.admin')], ['is_moderator', MessagesSquare, t('workspace.users.moderator')], ['is_writer', PenLine, t('workspace.users.writer')]] as const).map(([key, Icon, label]) => <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={Boolean(user[key])} disabled={saving === user.id} onChange={event => void update(user, { [key]: event.target.checked })} /><Icon className="size-3.5 text-primary" /><span>{label}</span></label>)}</div></td>
                  <td className="p-3"><p className="mb-2 text-xs text-content-muted">{loadingGrants ? t('workspace.adminUsers.loadingGrants') : t('workspace.adminUsers.activeGrantCount', { count: userGrantCount, total: SUPPORTED_CAPABILITY_COUNT })}</p><div className="flex gap-1.5"><button type="button" disabled={permissionBusy || !user.is_active || userGrantCount === SUPPORTED_CAPABILITY_COUNT} onClick={() => void grantAll(user)} className="app-button-primary app-button-sm">{grantSaving === user.id ? <Loader2 className="size-4 animate-spin" /> : <Shield className="size-4" />}{t('workspace.adminUsers.grantAll')}</button><button type="button" disabled={permissionBusy || !hasGrants} onClick={() => void revokeAll(user)} className="app-button-danger app-button-sm"><ShieldOff className="size-4" />{t('workspace.adminUsers.revokeAll')}</button></div></td>
                  <td className="p-3">{user.email ? <div className="grid gap-1.5"><button type="button" className="app-button-secondary app-button-sm" disabled={saving === user.id} onClick={() => void queueAccountEmail(user, 'verify')}>{t('identity.admin.resendVerification')}</button><button type="button" className="app-button-secondary app-button-sm" disabled={saving === user.id} onClick={() => void queueAccountEmail(user, 'reset')}>{t('identity.admin.sendReset')}</button></div> : '—'}</td>
                </tr>;
              })}</tbody>
            </Table>
            </TableContainer>
          </DataRegion>
          <nav className="ds-pagination" aria-label={t('workspace.adminUsers.pagination')}><button type="button" className="app-button-secondary app-button-sm" disabled={loadingMore || skip === 0} onClick={() => void loadWindow(Math.max(0, skip - PAGE_SIZE))}>{t('pagination.previous')}</button><span role="status" className="ds-pagination-status">{t('pagination.range', { start: skip + 1, end: skip + users.length })}</span><button type="button" className="app-button-secondary app-button-sm" disabled={loadingMore || !hasMore} onClick={() => void loadWindow(skip + PAGE_SIZE)}>{loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}{t('pagination.next')}</button></nav>
          </>}
        </>
      )}
    </div>
  );
}
