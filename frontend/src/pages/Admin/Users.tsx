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

  useEffect(() => {
    let active = true;
    Promise.all([
      guildManagementApi.getUsers(0, 500, { include_inactive: true, exclude_test_accounts: false }),
      guildManagementApi.getManageableGuilds(),
    ])
      .then(([loadedUsers, context]) => {
        if (!active) return;
        setUsers(loadedUsers);
        setGuilds(context.guilds);
        setSelectedGuild(context.guilds[0] || '');
      })
      .catch(() => active && setError(true))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

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

          <div className="grid gap-3">
            {users.map(user => {
              const userGrantCount = new Set(
                grants.filter(row => row.user_id === user.id).map(row => row.capability),
              ).size;
              const hasGrants = userGrantCount > 0;
              const permissionBusy = loadingGrants || grantSaving === user.id || !selectedGuild;
              return (
                <article key={user.id} className="admin-panel rounded-xl p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-semibold">{user.display_name || user.username}</h2>
                      <p className="text-sm text-content-muted">
                        {user.email || user.username} · {user.guild_name || t('workspace.common.noGuild')}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs ${user.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
                      {user.is_active ? t('workspace.users.active') : t('workspace.users.inactive')}
                    </span>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <label className="grid gap-1 text-sm">
                      <span className="text-content-muted">{t('workspace.users.guildRank')}</span>
                      <select
                        value={user.guild_rank || 'Unranked'}
                        onChange={event => void update(user, { guild_rank: event.target.value })}
                        className="admin-secondary min-h-11 rounded-lg bg-transparent px-3"
                      >
                        <option>Unranked</option><option>Member</option><option>Vice Leader</option><option>Leader</option>
                      </select>
                    </label>
                    {([
                      ['is_superuser', Shield, t('workspace.users.admin')],
                      ['is_moderator', MessagesSquare, t('workspace.users.moderator')],
                      ['is_writer', PenLine, t('workspace.users.writer')],
                    ] as const).map(([key, Icon, label]) => (
                      <label key={key} className="admin-secondary flex min-h-11 items-center gap-2 rounded-lg px-3">
                        <input
                          type="checkbox"
                          checked={Boolean(user[key])}
                          disabled={saving === user.id}
                          onChange={event => void update(user, { [key]: event.target.checked })}
                        />
                        <Icon className="h-4 w-4 text-primary" /><span>{label}</span>
                      </label>
                    ))}
                  </div>
                  {selectedGuild && (
                    <div className="admin-secondary mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg p-3">
                      <div>
                        <p className="text-sm font-medium">{t('workspace.adminUsers.selectedGuildPermissions', { guild: selectedGuild })}</p>
                        <p className="text-xs text-content-muted">
                          {loadingGrants
                            ? t('workspace.adminUsers.loadingGrants')
                            : t('workspace.adminUsers.activeGrantCount', { count: userGrantCount, total: SUPPORTED_CAPABILITY_COUNT })}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={permissionBusy || !user.is_active || userGrantCount === SUPPORTED_CAPABILITY_COUNT}
                          onClick={() => void grantAll(user)}
                          className="app-button-primary"
                        >
                          {grantSaving === user.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                          {t('workspace.adminUsers.grantAll')}
                        </button>
                        <button
                          type="button"
                          disabled={permissionBusy || !hasGrants}
                          onClick={() => void revokeAll(user)}
                          className="app-button-danger"
                        >
                          <ShieldOff className="h-4 w-4" />
                          {t('workspace.adminUsers.revokeAll')}
                        </button>
                      </div>
                    </div>
                  )}
                  {saving === user.id && (
                    <p className="mt-2 flex items-center gap-2 text-xs text-content-muted">
                      <Save className="h-3 w-3 animate-pulse" />{t('workspace.users.saving')}
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
