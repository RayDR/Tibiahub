import type { GuildAccessContext } from '../services/guildManagement';
import { useOutletContext } from 'react-router-dom';

export interface GuildLayoutContext {
    selectedGuild: string;
    guildContext: GuildAccessContext;
}

export function resolveGuildContext(selectedGuild?: string): string | undefined {
    const selected = (selectedGuild || '').trim();
    return selected || undefined;
}

export function useGuildContext(_user?: unknown): string | undefined {
    const context = useOutletContext<GuildLayoutContext>();
    return resolveGuildContext(context?.selectedGuild);
}
