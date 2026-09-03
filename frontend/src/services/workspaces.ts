import api from './api';

export type WorkspaceRole = 'global_admin' | 'guild_leader' | 'guild_viceleader' | 'guild_member' | 'delegated_manager';

export interface GuildDirectoryEntry {
  key: string; name: string; world_name?: string; leader?: string; member_count: number;
  is_active: boolean; setup_status: 'ready' | 'needs_attention'; recent_sync_at?: string;
  open_alerts: number; raffle_issues: number;
}

export interface AdminGuildWorkspace {
  workspace: { type: 'admin_guild_assist'; admin_user_id: number; guild_name: string };
  guild: GuildDirectoryEntry;
  audit_notice: boolean;
}

export interface WorkspaceAuditEntry {
  id: number;
  action: string;
  target_type?: string;
  target_id?: string;
  created_at: string;
  safe_metadata?: Record<string, unknown>;
}

export interface WorkspaceAuditPage {
  items: WorkspaceAuditEntry[];
  total: number;
  skip: number;
  limit: number;
}

export const workspaceApi = {
  async guilds(): Promise<GuildDirectoryEntry[]> { return (await api.get('/admin/guilds')).data; },
  async adminGuild(key: string): Promise<AdminGuildWorkspace> { return (await api.get(`/admin/guilds/${encodeURIComponent(key)}`)).data; },
  async guildAudits(key: string, skip = 0, limit = 20, signal?: AbortSignal): Promise<WorkspaceAuditPage> {
    return (await api.get(`/admin/guilds/${encodeURIComponent(key)}/audits`, { params: { skip, limit, paged: true }, signal })).data;
  },
};
