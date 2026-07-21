import type { User } from '../services/auth';

export function resolveGuildContext(user: User | null | undefined): string | undefined {
    const ownGuild = (user?.guild_name || '').trim();
    if (!user?.is_superuser) return ownGuild || undefined;

    const selectedGuild = (localStorage.getItem('selectedGuildName') || '').trim();
    return selectedGuild || ownGuild || undefined;
}
