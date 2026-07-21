import { Outlet, Link, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Activity, Settings, Users, Database, LogOut, Shield, Wrench } from 'lucide-react';

export default function AdminLayout() {
    const { t } = useTranslation();
    const { user, logout, loading, isAuthenticated } = useAuth();
    const location = useLocation();

    if (loading) {
        return <div className="text-center mt-20 text-[color:var(--color-text-muted)]">Loading admin panel...</div>;
    }

    if (!isAuthenticated || !user?.is_superuser) {
        return <Navigate to="/guild" replace />;
    }

    const navSections = [
        {
            title: 'Core',
            items: [
                { name: 'Overview', path: '/admin/overview', icon: Activity },
                { name: 'Guild Management', path: '/admin/management', icon: Users },
                { name: 'Guild Preview', path: '/admin/guild-view', icon: Shield },
                { name: 'Bestiary', path: '/admin/bestiary', icon: Database },
                { name: t('admin.settings'), path: '/admin/settings', icon: Settings },
            ],
        },
        {
            title: 'Data Ops',
            items: [
                { name: 'Data Tools', path: '/admin/data-tools', icon: Wrench },
            ],
        },
    ];

    return (
        <div className="flex flex-col lg:flex-row min-h-[calc(100vh-100px)] gap-4 lg:gap-6 mt-4 sm:mt-8 px-2 sm:px-0">
            {/* Sidebar */}
            <aside className="w-full lg:w-64 flex-shrink-0">
                <div className="app-surface rounded-lg overflow-hidden lg:sticky lg:top-24">
                    <div className="p-3 sm:p-4 border-b border-[color:var(--color-border)] bg-[color:var(--color-surface-alt)]">
                        <h3 className="font-serif text-[color:var(--color-primary)] font-bold text-base sm:text-lg tracking-wide flex items-center gap-2">
                            <Shield className="w-4 h-4 sm:w-5 sm:h-5" />
                            {t('admin.adminPanel')}
                        </h3>
                        <p className="text-xs text-[color:var(--color-text-muted)] mt-1 truncate">
                            {user?.username}
                        </p>
                        <span className="text-xs text-[color:var(--color-primary)]/80 uppercase tracking-widest font-semibold text-[10px]">
                            {t('admin.administrator')}
                        </span>
                    </div>

                    <nav className="p-2 space-y-3">
                        {navSections.map((section) => (
                            <div key={section.title}>
                                <div className="px-2 py-1 text-[10px] uppercase tracking-widest text-[color:var(--color-text-muted)]">
                                    {section.title}
                                </div>
                                <div className="space-y-1">
                                    {section.items.map((item) => {
                                        const isActive = location.pathname === item.path;
                                        const Icon = item.icon;
                                        return (
                                            <Link
                                                key={item.path}
                                                to={item.path}
                                                className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors text-sm font-medium ${isActive
                                                        ? 'bg-[color:var(--color-primary)]/20 text-[color:var(--color-primary)] border border-[color:var(--color-primary)]/30'
                                                        : 'text-[color:var(--color-text-muted)] hover:text-[color:var(--color-text)] hover:bg-[color:var(--color-surface-alt)]'
                                                    }`}
                                            >
                                                <Icon className="w-4 h-4" />
                                                {item.name}
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </nav>

                    <div className="p-2 border-t border-[color:var(--color-border)] mt-2">
                        <Link
                            to="/guild"
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-[color:var(--color-text-muted)] hover:text-[color:var(--color-primary)] hover:bg-[color:var(--color-primary)]/10 transition-colors text-sm font-medium mb-2"
                        >
                            <Shield className="w-4 h-4" />
                            {t('nav.guild')}
                        </Link>
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
            <main className="flex-1 app-surface rounded-lg p-3 sm:p-6 min-h-[500px]">
                <Outlet />
            </main>
        </div>
    );
}
