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

function StatCard({ label, value, sub, color = 'text-slate-100' }: { label: string; value: string | number; sub?: string; color?: string }) {
    return (
        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
            <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">{label}</div>
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
            {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
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
        if (status === 'online') return 'text-green-400';
        if (status === 'offline') return 'text-red-400';
        return 'text-yellow-400';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <Activity className="w-5 h-5 text-amber-500" />
                    <div>
                        <h1 className="text-xl font-semibold text-slate-100">System Overview</h1>
                        <p className="text-sm text-slate-400">Live snapshot of all platform data.</p>
                    </div>
                </div>
                <button
                    onClick={() => void load(true)}
                    disabled={refreshing}
                    className="flex items-center gap-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* API / Sync Status */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <Globe className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium text-slate-300">Tibia API</span>
                    </div>
                    {tibiaStatus ? (
                        <div className="flex items-center gap-3">
                            <span className={`text-2xl font-bold uppercase ${statusColor(tibiaStatus.status)}`}>
                                {tibiaStatus.status}
                            </span>
                            {Number.isFinite(Number(tibiaStatus.latency_ms)) && tibiaStatus.latency_ms !== null && (
                                <span className="text-xs text-slate-500">{Number(tibiaStatus.latency_ms).toFixed(0)}ms</span>
                            )}
                        </div>
                    ) : (
                        <span className="text-slate-500 text-sm">Unavailable</span>
                    )}
                    {tibiaStatus?.message && <p className="text-xs text-slate-500 mt-1">{tibiaStatus.message}</p>}
                </div>

                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <Database className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium text-slate-300">Data Version</span>
                    </div>
                    <div className="text-2xl font-bold text-slate-100 truncate">
                        {dataVersion ?? <span className="text-slate-500 text-base">Unavailable</span>}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">Latest external sync version</p>
                </div>
            </div>

            {/* Creatures */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
                    <Bug className="w-3.5 h-3.5" /> Bestiary
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <StatCard label="Total Creatures" value={stats?.creatures.total ?? '—'} />
                    <StatCard label="Visible" value={stats?.creatures.visible ?? '—'} color="text-green-400" sub="Public in cyclopedia" />
                    <StatCard label="Hidden" value={stats?.creatures.hidden ?? '—'} color="text-red-400" sub="Admin-only" />
                </div>
            </div>

            {/* Content */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
                    <ScrollText className="w-3.5 h-3.5" /> Content
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <StatCard label="Quests" value={stats?.quests.total ?? '—'} />
                    <StatCard label="Hunt Zones" value={stats?.hunt_zones.total ?? '—'} />
                    <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5 flex items-center justify-center text-slate-600 text-xs italic">
                        More data coming soon
                    </div>
                </div>
            </div>

            {/* Users */}
            <div>
                <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
                    <Users className="w-3.5 h-3.5" /> Users
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Total Users" value={stats?.users.total ?? '—'} />
                    <StatCard label="Active" value={stats?.users.active ?? '—'} color="text-green-400" />
                    <StatCard label="Inactive" value={stats?.users.inactive ?? '—'} color="text-slate-500" />
                    <StatCard label="Admins" value={stats?.users.admin ?? '—'} color="text-amber-400" />
                </div>
            </div>
        </div>
    );
}
