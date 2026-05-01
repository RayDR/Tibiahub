
import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, Megaphone, CalendarClock, Users, LogOut, Shield, Compass, Sparkles, Coins } from 'lucide-react';

export default function GuildLayout() {
    const { t } = useTranslation();
    const { user, logout, loading, isAuthenticated } = useAuth();
    const location = useLocation();

    if (loading) {
        return <div className="text-center mt-20 text-slate-400">Loading guild data...</div>;
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    const navItems = [
        { name: t('guild.dashboard'), path: '/guild/dashboard', icon: LayoutDashboard, special: false },
        { name: t('guild.announcements'), path: '/guild/announcements', icon: Megaphone, special: false },
        { name: t('guild.eventsHunts'), path: '/guild/events', icon: CalendarClock, special: false },
        { name: t('guild.huntCatalog'), path: '/guild/hunts', icon: Compass, special: false },
        { name: t('guild.recruitment'), path: '/guild/recruitment', icon: Users, special: true },
        { name: 'Guild Raffle', path: '/guild/raffle', icon: Coins, special: true },
    ];

    return (
        <div className="flex flex-col lg:flex-row min-h-[calc(100vh-100px)] gap-4 lg:gap-6 mt-6 sm:mt-8 px-2 sm:px-0">
            {/* Sidebar */}
            <aside className="w-full lg:w-64 flex-shrink-0">
                <div className="bg-slate-900/50 border border-red-900/30 rounded-lg overflow-hidden lg:sticky lg:top-24">
                    <div className="p-3 sm:p-4 border-b border-red-900/30 bg-slate-900/80">
                        <h3 className="font-serif text-primary font-bold text-lg tracking-wide flex items-center gap-2">
                            <Shield className="w-5 h-5 text-red-500" />
                            {t('guild.guildHall')}
                        </h3>
                        <p className="text-xs text-slate-400 mt-1 truncate">
                            {user?.tibia_character_name}
                        </p>
                        <span className="text-xs text-primary/80 uppercase tracking-widest font-semibold text-[10px]">
                            {user?.guild_rank || 'Not Ranked'}
                        </span>
                    </div>

                    <nav className="p-2 space-y-1">
                        {navItems.map((item) => {
                            const isActive = location.pathname === item.path;
                            const Icon = item.icon;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors text-sm font-medium ${isActive
                                            ? 'bg-red-600/20 text-primary border border-red-500/20'
                                            : 'text-slate-400 hover:text-primary hover:bg-red-950/10'
                                        }`}
                                >
                                    <Icon className={`w-4 h-4 ${item.special ? 'text-yellow-400' : ''}`} />
                                    {item.name}
                                    {item.special && (
                                        <Sparkles className="w-3 h-3 text-yellow-400 ml-auto" />
                                    )}
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="p-2 border-t border-red-900/30 mt-2">
                        <button
                            onClick={logout}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors text-sm font-medium"
                        >
                            <LogOut className="w-4 h-4" />
                            {t('auth.logout')}
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 bg-slate-900/30 border border-red-900/20 rounded-lg p-6 min-h-[500px] shadow-lg shadow-red-950/10 transition-all duration-300">
                <Outlet />
            </main>
        </div>
    );
}
