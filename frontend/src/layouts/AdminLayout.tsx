import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Settings, Users, Database, LogOut, Shield, GitBranch } from 'lucide-react';

export default function AdminLayout() {
    const { t } = useTranslation();
    const { user, logout, loading, isAuthenticated } = useAuth();
    const location = useLocation();

    if (loading) {
        return <div className="text-center mt-20 text-slate-400">Loading admin panel...</div>;
    }

    if (!isAuthenticated || !user?.is_superuser) {
        return <Navigate to="/guild" replace />;
    }

    const navItems = [
        { name: t('admin.management'), path: '/admin/management', icon: Users },
        { name: 'API Monitor', path: '/admin/api-monitor', icon: Database },
        { name: 'Database Sync', path: '/admin/database-sync', icon: GitBranch },
        { name: 'Admin Sync', path: '/admin/sync', icon: GitBranch },
        { name: t('admin.settings'), path: '/admin/settings', icon: Settings },
    ];

    return (
        <div className="flex flex-col lg:flex-row min-h-[calc(100vh-100px)] gap-4 lg:gap-6 mt-4 sm:mt-8 px-2 sm:px-0">
            {/* Sidebar */}
            <aside className="w-full lg:w-64 flex-shrink-0">
                <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg overflow-hidden lg:sticky lg:top-24">
                    <div className="p-3 sm:p-4 border-b border-slate-700/50 bg-slate-900/80">
                        <h3 className="font-serif text-red-500 font-bold text-base sm:text-lg tracking-wide flex items-center gap-2">
                            <Shield className="w-4 h-4 sm:w-5 sm:h-5" />
                            {t('admin.adminPanel')}
                        </h3>
                        <p className="text-xs text-slate-400 mt-1 truncate">
                            {user?.username}
                        </p>
                        <span className="text-xs text-red-400/80 uppercase tracking-widest font-semibold text-[10px]">
                            {t('admin.administrator')}
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
                                            ? 'bg-red-600/20 text-red-500 border border-red-500/20'
                                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                                        }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {item.name}
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="p-2 border-t border-slate-700/50 mt-2">
                        <Link
                            to="/guild"
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-slate-400 hover:text-amber-400 hover:bg-amber-950/30 transition-colors text-sm font-medium mb-2"
                        >
                            <Shield className="w-4 h-4" />
                            {t('nav.guild')}
                        </Link>
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
            <main className="flex-1 bg-slate-900/30 border border-slate-700/30 rounded-lg p-3 sm:p-6 min-h-[500px]">
                <Outlet />
            </main>
        </div>
    );
}
