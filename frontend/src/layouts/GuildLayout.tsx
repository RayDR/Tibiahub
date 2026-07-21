
import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, Megaphone, CalendarClock, Users, LogOut, Shield, Compass, Sparkles, Coins } from 'lucide-react';
import { guildApi } from '../services/guild';
import { guildManagementApi } from '../services/guildManagement';
import { REQUEST_TIMEOUT_MS } from '../services/api';

export default function GuildLayout() {
    const { t } = useTranslation();
    const { user, logout, loading, isAuthenticated } = useAuth();
    const location = useLocation();
    const [featureFlags, setFeatureFlags] = useState({
        guild_raffles_enabled: true,
        guild_contests_enabled: true,
    });
    const [availableGuilds, setAvailableGuilds] = useState<string[]>([]);
    const [selectedGuild, setSelectedGuild] = useState('');
    const [authTimedOut, setAuthTimedOut] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const controller = new AbortController();

        const loadFlags = async () => {
            try {
                const flags = await guildApi.getFeatureFlags(controller.signal, 3000);
                if (!cancelled) {
                    setFeatureFlags(flags);
                }
            } catch {
                // keep defaults if endpoint is unavailable
            }
        };
        void loadFlags();

        return () => {
            cancelled = true;
            controller.abort();
        };
    }, []);

    useEffect(() => {
        if (!loading) {
            setAuthTimedOut(false);
            return;
        }

        const timer = window.setTimeout(() => {
            setAuthTimedOut(true);
        }, REQUEST_TIMEOUT_MS + 2000);

        return () => {
            window.clearTimeout(timer);
        };
    }, [loading]);

    const navItems = useMemo(() => [
        { name: t('guild.dashboard'), path: '/guild/dashboard', icon: LayoutDashboard, special: false },
        { name: 'Members', path: '/guild/members', icon: Users, special: false },
        { name: t('guild.announcements'), path: '/guild/announcements', icon: Megaphone, special: false },
        { name: 'Guild Events', path: '/guild/events', icon: CalendarClock, special: false },
        { name: 'Contests', path: '/guild/events?type=contest', icon: Shield, special: true },
        { name: t('guild.huntCatalog'), path: '/guild/hunts', icon: Compass, special: false },
        ...(featureFlags.guild_raffles_enabled ? [{ name: 'Guild Raffle', path: '/guild/raffle', icon: Coins, special: true }] : []),
    ], [t, featureFlags.guild_raffles_enabled]);

    useEffect(() => {
        const loadGuildSelector = async () => {
            if (!user?.is_superuser) {
                const ownGuild = (user?.guild_name || '').trim();
                if (ownGuild) {
                    localStorage.setItem('selectedGuildName', ownGuild);
                    setSelectedGuild(ownGuild);
                }
                return;
            }

            try {
                const guilds = await guildManagementApi.getGuilds();
                const normalizedGuilds = guilds.filter((name) => Boolean(name && name.trim()));
                setAvailableGuilds(normalizedGuilds);

                const saved = (localStorage.getItem('selectedGuildName') || '').trim();
                const defaultGuild = normalizedGuilds.includes('Bloodborne Warhowl')
                    ? 'Bloodborne Warhowl'
                    : normalizedGuilds[0] || 'Bloodborne Warhowl';
                const nextGuild = normalizedGuilds.includes(saved) ? saved : defaultGuild;

                if (nextGuild) {
                    setSelectedGuild(nextGuild);
                    localStorage.setItem('selectedGuildName', nextGuild);
                }
            } catch {
                const fallbackGuild = (user?.guild_name || 'Bloodborne Warhowl').trim();
                if (fallbackGuild) {
                    setSelectedGuild(fallbackGuild);
                    localStorage.setItem('selectedGuildName', fallbackGuild);
                }
            }
        };

        void loadGuildSelector();
    }, [user?.is_superuser, user?.guild_name]);

    if (loading) {
        if (authTimedOut) {
            return (
                <div className="mt-20 text-center text-[color:var(--color-text)]">
                    <p className="mb-3">Unable to load guild data right now.</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="rounded-md border border-[color:var(--color-danger)]/40 bg-[color:var(--color-danger)]/20 px-4 py-2 text-sm hover:bg-[color:var(--color-danger)]/30"
                    >
                        Retry
                    </button>
                </div>
            );
        }
        return <div className="text-center mt-20 text-[color:var(--color-text-muted)]">Loading guild data...</div>;
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return (
        <div className="flex flex-col lg:flex-row min-h-[calc(100vh-100px)] gap-4 lg:gap-6 mt-6 sm:mt-8 px-2 sm:px-0">
            {/* Sidebar */}
            <aside className="w-full lg:w-64 flex-shrink-0">
                <div className="app-surface rounded-lg overflow-hidden lg:sticky lg:top-24">
                    <div className="p-3 sm:p-4 border-b border-[color:var(--color-border)] bg-[color:var(--color-surface-alt)]">
                        <h3 className="font-serif text-primary font-bold text-lg tracking-wide flex items-center gap-2">
                            <Shield className="w-5 h-5 text-[color:var(--color-primary)]" />
                            {t('guild.guildHall')}
                        </h3>
                        <p className="text-xs text-[color:var(--color-text-muted)] mt-1 truncate">
                            {user?.tibia_character_name}
                        </p>
                        <span className="text-xs text-primary/80 uppercase tracking-widest font-semibold text-[10px]">
                            {user?.guild_rank || 'Not Ranked'}
                        </span>
                        {user?.is_superuser && availableGuilds.length > 0 && (
                            <div className="mt-3">
                                <label className="mb-1 block text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">Managing guild</label>
                                <select
                                    value={selectedGuild}
                                    onChange={(e) => {
                                        const nextGuild = e.target.value;
                                        setSelectedGuild(nextGuild);
                                        localStorage.setItem('selectedGuildName', nextGuild);
                                    }}
                                    className="app-input h-8 w-full rounded-md px-2 py-1 text-xs"
                                >
                                    {availableGuilds.map((guildName) => (
                                        <option key={guildName} value={guildName}>{guildName}</option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    <nav className="p-2 space-y-1">
                        {navItems.map((item) => {
                            const eventType = new URLSearchParams(location.search).get('type');
                            const isContestShortcut = item.path === '/guild/events?type=contest';
                            const isActive = isContestShortcut
                                ? (location.pathname === '/guild/events' && eventType === 'contest')
                                : location.pathname === item.path;
                            const Icon = item.icon;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors text-sm font-medium ${isActive
                                            ? 'bg-[color:var(--color-primary)]/20 text-[color:var(--color-primary)] border border-[color:var(--color-primary)]/30'
                                            : 'text-[color:var(--color-text-muted)] hover:text-[color:var(--color-primary)] hover:bg-[color:var(--color-primary)]/10'
                                        }`}
                                >
                                    <Icon className={`w-4 h-4 ${item.special ? 'text-[color:var(--color-warning)]' : ''}`} />
                                    {item.name}
                                    {item.special && (
                                        <Sparkles className="w-3 h-3 text-[color:var(--color-warning)] ml-auto" />
                                    )}
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="p-2 border-t border-[color:var(--color-border)] mt-2">
                        <button
                            onClick={logout}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-[color:var(--color-text-muted)] hover:text-[color:var(--color-danger)] hover:bg-[color:var(--color-danger)]/15 transition-colors text-sm font-medium"
                        >
                            <LogOut className="w-4 h-4" />
                            {t('auth.logout')}
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 app-surface rounded-lg p-6 min-h-[500px] shadow-lg transition-all duration-300">
                <Outlet />
            </main>
        </div>
    );
}
