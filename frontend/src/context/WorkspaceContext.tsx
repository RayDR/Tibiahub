import { createContext, ReactNode, useContext, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import type { WorkspaceRole } from '../services/workspaces';

export type WorkspaceContextValue =
  | { type: 'public' }
  | { type: 'personal'; userId: number }
  | { type: 'guild'; guildName: string; role: WorkspaceRole }
  | { type: 'admin'; adminUserId: number }
  | { type: 'admin_guild_assist'; adminUserId: number; guildKey: string };

const Context = createContext<WorkspaceContextValue>({ type: 'public' });

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const value = useMemo<WorkspaceContextValue>(() => {
    if (!user) return { type: 'public' };
    const assistance = pathname.match(/^\/admin\/guilds\/([^/]+)/);
    if (user.is_superuser && assistance) return { type: 'admin_guild_assist', adminUserId: user.id, guildKey: assistance[1] };
    if (pathname.startsWith('/admin') && user.is_superuser) return { type: 'admin', adminUserId: user.id };
    // This value is presentational only. Canonical guild authorization and the
    // selected role are loaded from /guild-management/context by GuildLayout.
    const selectedGuild = localStorage.getItem(`tibiahub:selectedGuild:${user.id}`);
    if (pathname.startsWith('/guild') && selectedGuild) return { type: 'guild', guildName: selectedGuild, role: 'guild_member' };
    return { type: 'personal', userId: user.id };
  }, [pathname, user]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useWorkspace() { return useContext(Context); }
