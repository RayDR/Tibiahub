import axios from 'axios';
import { useEffect, useState } from 'react';
import { KeyRound, Loader2, MessagesSquare, PenLine, Save, Shield, ShieldOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import {
  guildManagementApi,
  GuildManagementGrant,
  GuildMember,
} from '../../services/guildManagement';
import AdminIdentityLinker from '../../components/admin/AdminIdentityLinker';
import { adminEmailApi } from '../../services/adminEmail';

const SUPPORTED_CAPABILITY_COUNT = 4;

function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return fallback;
}

export default function AdminUsers() {
  const { t } = useTranslation();
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

  useEffect(() => {
    let active = true;
    Promise.all([
      guildManagementApi.getUsers(0, 50, { include_inactive: true, exclude_test_accounts: false }),
      guildManagementApi.getManageableGuilds(),
    ])
      .then(([loadedUsers, context]) => {
        if (!active) return;
        setUsers(loadedUsers);
        setHasMore(loadedUsers.length === 50);
        setGuilds(context.guilds);
        setSelectedGuild(context.guilds[0] || '');
      })
      .catch(() => active && setError(true))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const rows = await guildManagementApi.getUsers(users.length, 50, { include_inactive: true, exclude_test_accounts: false });
      setUsers((current) => [...current, ...rows]);
      setHasMore(rows.length === 50);
    } catch {
      showError(t('workspace.errors.tryAgain'));
    } finally {
      setLoadingMore(false);
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
      if (kind === 'verify') await adminEmailApi.verify(user.id, 'en');
      else await adminEmailApi.reset(user.id, 'en');
      showSuccess(t(`identity.admin.${kind}Queued`));
    } catch { showError(t('identity.emailAdmin.error')); }
    finally { setSaving(null); }
  };

  return (
    <div className="space-y-4">
      <WorkspaceHeader
        title={t('workspace.adminUsers.title')}
        subtitle={t('workspace.adminUsers.subtitle')}
        badge={t('workspace.admin.badge')}
      />
      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>
      ) : error ? (
        <EmptyState title={t('workspace.errors.users')} description={t('workspace.errors.tryAgain')} />
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

          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[72rem] text-left text-sm">
              <thead className="bg-surface-raised text-xs uppercase tracking-wide text-content-muted"><tr><th className="p-3">User</th><th className="p-3">Status</th><th className="p-3">Roles</th><th className="p-3">Guild permissions</th><th className="p-3">Actions</th></tr></thead>
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
            </table>
          </div>
          {hasMore ? <div className="flex justify-center"><button type="button" className="app-button-secondary" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}{loadingMore ? t('common.loading') : 'Load more users'}</button></div> : null}
        </>
      )}
    </div>
  );
}
