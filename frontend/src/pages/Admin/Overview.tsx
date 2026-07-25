import { useEffect, useState } from 'react';
import { adminOverviewApi, systemApi } from '../../services/api';
import { guildManagementApi } from '../../services/guildManagement';
import { Activity, Bug, Database, Globe, Loader2, RefreshCw, ScrollText, Users } from 'lucide-react';

interface Stats {
    creatures: { total: number; visible: number; hidden: number };
    hunt_zones: { total: number };
    quests: { total: number };
    users: { total: number; active: number; inactive: number; admin: number };
}

interface TibiaStatus {
    status: 'online' | 'offline' | 'degraded';
    latency_ms?: number | null;
    message: string;
    last_check: string;
}

function StatCard({ label, value, sub, color = 'text-content-primary' }: { label: string; value: string | number; sub?: string; color?: string }) {
    return (
        <div className="admin-panel rounded-xl p-5">
            <div className="text-xs text-content-secondary uppercase tracking-wide mb-1">{label}</div>
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
            {sub && <div className="text-xs text-content-muted mt-1">{sub}</div>}
        </div>
    );
}

export default function Overview() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [tibiaStatus, setTibiaStatus] = useState<TibiaStatus | null>(null);
    const [dataVersion, setDataVersion] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const load = async (isRefresh = false) => {
        if (isRefresh) setRefreshing(true);
        else setLoading(true);
        try {
            const [statsData, tibiaData, healthData] = await Promise.allSettled([
                adminOverviewApi.getStats(),
                guildManagementApi.getTibiaAPIStatus(),
                systemApi.getHealth(),
            ]);
            if (statsData.status === 'fulfilled') setStats(statsData.value);
            if (tibiaData.status === 'fulfilled') setTibiaStatus(tibiaData.value);
            if (healthData.status === 'fulfilled') {
                setDataVersion(healthData.value.external_sync?.latest_data_version ?? null);
            }
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { void load(); }, []);

    const statusColor = (status?: string) => {
        if (status === 'online') return 'text-success';
        if (status === 'offline') return 'text-danger';
        return 'text-primary';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="admin-panel rounded-xl p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <Activity className="w-5 h-5 text-primary" />
                    <div>
                        <h1 className="text-xl font-semibold text-content-primary">System Overview</h1>
                        <p className="text-sm text-content-secondary">Live snapshot of all platform data.</p>
                    </div>
                </div>
                <button
                    onClick={() => void load(true)}
                    disabled={refreshing}
                    className="admin-secondary flex items-center gap-2 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* API / Sync Status */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="admin-panel rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <Globe className="w-4 h-4 text-content-secondary" />
                        <span className="text-sm font-medium text-content-secondary">Tibia API</span>
                    </div>
                    {tibiaStatus ? (
                        <div className="flex items-center gap-3">
                            <span className={`text-2xl font-bold uppercase ${statusColor(tibiaStatus.status)}`}>
                                {tibiaStatus.status}
                            </span>
                            {Number.isFinite(Number(tibiaStatus.latency_ms)) && tibiaStatus.latency_ms !== null && (
                                <span className="text-xs text-content-muted">{Number(tibiaStatus.latency_ms).toFixed(0)}ms</span>
                            )}
                        </div>
                    ) : (
                        <span className="text-content-muted text-sm">Unavailable</span>
                    )}
                    {tibiaStatus?.message && <p className="text-xs text-content-muted mt-1">{tibiaStatus.message}</p>}
                </div>

                <div className="admin-panel rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <Database className="w-4 h-4 text-content-secondary" />
                        <span className="text-sm font-medium text-content-secondary">Data Version</span>
                    </div>
                    <div className="text-2xl font-bold text-content-primary truncate">
                        {dataVersion ?? <span className="text-content-muted text-base">Unavailable</span>}
                    </div>
                    <p className="text-xs text-content-muted mt-1">Latest external sync version</p>
                </div>
            </div>

            {/* Creatures */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-content-muted mb-3 flex items-center gap-2">
                    <Bug className="w-3.5 h-3.5" /> Bestiary
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <StatCard label="Total Creatures" value={stats?.creatures.total ?? '—'} />
                    <StatCard label="Visible" value={stats?.creatures.visible ?? '—'} color="text-success" sub="Public in cyclopedia" />
                    <StatCard label="Hidden" value={stats?.creatures.hidden ?? '—'} color="text-danger" sub="Admin-only" />
                </div>
            </div>

            {/* Content */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-content-muted mb-3 flex items-center gap-2">
                    <ScrollText className="w-3.5 h-3.5" /> Content
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <StatCard label="Quests" value={stats?.quests.total ?? '—'} />
                    <StatCard label="Hunt Zones" value={stats?.hunt_zones.total ?? '—'} />
                    <div className="admin-panel-muted rounded-xl p-5 flex items-center justify-center text-content-muted text-xs italic">
                        No additional metrics available
                    </div>
                </div>
            </div>

            {/* Users */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-content-muted mb-3 flex items-center gap-2">
                    <Users className="w-3.5 h-3.5" /> Users
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Total Users" value={stats?.users.total ?? '—'} />
                    <StatCard label="Active" value={stats?.users.active ?? '—'} color="text-success" />
                    <StatCard label="Inactive" value={stats?.users.inactive ?? '—'} color="text-content-muted" />
                    <StatCard label="Admins" value={stats?.users.admin ?? '—'} color="text-primary" />
                </div>
            </div>
        </div>
    );
}
