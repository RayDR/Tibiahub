import type { User } from '../services/auth';
import type { GuildAccessContext } from '../services/guildManagement';
import { useOutletContext } from 'react-router-dom';

export interface GuildLayoutContext {
    selectedGuild: string;
    guildContext: GuildAccessContext;
}

export function resolveGuildContext(user: User | null | undefined, selectedGuild?: string): string | undefined {
    const selected = (selectedGuild || '').trim();
    const ownGuild = (user?.guild_name || '').trim();
    return selected || ownGuild || undefined;
}

export function useGuildContext(user: User | null | undefined): string | undefined {
    const context = useOutletContext<GuildLayoutContext>();
    return resolveGuildContext(user, context?.selectedGuild);
}
