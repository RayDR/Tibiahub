import type { User } from '../services/auth';
import { useOutletContext } from 'react-router-dom';

export interface GuildLayoutContext {
    selectedGuild: string;
}

export function resolveGuildContext(user: User | null | undefined, selectedGuild?: string): string | undefined {
    const ownGuild = (user?.guild_name || '').trim();
    if (!user?.is_superuser) return ownGuild || undefined;

    const selected = (selectedGuild || '').trim();
    return selected || ownGuild || undefined;
}

export function useGuildContext(user: User | null | undefined): string | undefined {
    const context = useOutletContext<GuildLayoutContext>();
    return resolveGuildContext(user, context?.selectedGuild);
}
