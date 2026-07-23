/**
 * DataTools – consolidated page for API Monitor, Database Sync, and Admin Sync.
 * Replaces three separate admin pages with a single tabbed interface.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useToast } from '../../context/ToastContext';
import {
    CheckCircle, XCircle, AlertCircle, Loader2,
    RefreshCw, Database, Globe, BookOpen, Code, Clock,
    GitBranch, Download, Eye,
    Workflow,
} from 'lucide-react';
import KnowledgeOperations from './KnowledgeOperations';

type Tab = 'api-monitor' | 'db-sync' | 'admin-sync' | 'knowledge';

// ── API Monitor types ──────────────────────────────────────────────────────────
interface APIStatus {
    name: string;
    url: string;
    status: 'online' | 'offline' | 'error';
    status_code?: number;
    latency_ms?: number;
    error?: string;
    sample_data?: any;
    full_response?: any;
}
interface APIMonitorResponse {
    timestamp: string;
    total_apis: number;
    online_count: number;
    apis: APIStatus[];
}

// ── DB Sync types ──────────────────────────────────────────────────────────────
interface SyncChange {
    timestamp: string;
    change_type: string;
    source_api: string;
    entity: string;
    entity_id: number;
    action: string;
    old_data?: any;
    new_data?: any;
    status: string;
    approval_required: boolean;
}
interface SyncPreview {
    status: string;
    message: string;
    backup_created: boolean;
    total_changes: number;
    pending_approvals: number;
    changes: SyncChange[];
    action_required: boolean;
}

// ── Admin Sync types ───────────────────────────────────────────────────────────
interface SyncLog {
    id: number;
    api_name: string;
    endpoint: string;
    status: 'pending' | 'running' | 'success' | 'error';
    source?: string;
    total_items?: number;
    processed_items: number;
    error_count: number;
    message?: string;
    started_at: string;
    completed_at?: string;
}
interface SyncStats {
    creatures: number;
    items: number;
    hunting_places: number;
    quests: number;
    sync_logs: number;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

function authHeader() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function getStatusIcon(status: string) {
    if (status === 'online' || status === 'success') return <CheckCircle className="w-4 h-4 text-green-400" />;
    if (status === 'offline' || status === 'error') return <XCircle className="w-4 h-4 text-red-400" />;
    return <AlertCircle className="w-4 h-4 text-yellow-400" />;
}

// ── API Monitor tab ────────────────────────────────────────────────────────────
function APIMonitorTab() {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<APIMonitorResponse | null>(null);
    const [expandedAPI, setExpandedAPI] = useState<string | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const response = await axios.get<APIMonitorResponse>(
                `${API_BASE}/guild-management/api-monitor`,
                { headers: authHeader() }
            );
            setData(response.data);
        } catch { /* ignore */ }
        finally { setLoading(false); }
    };

    useEffect(() => { void load(); }, []);

    if (loading) return <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                {data && (
                    <div className="flex gap-4 text-sm text-slate-400">
                        <span><span className="text-slate-200 font-medium">{data.total_apis}</span> APIs</span>
                        <span><span className="text-green-400 font-medium">{data.online_count}</span> online</span>
                        <span>checked {new Date(data.timestamp).toLocaleTimeString()}</span>
                    </div>
                )}
                <button onClick={load} className="flex items-center gap-1 rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200">
                    <RefreshCw className="w-3.5 h-3.5" /> Refresh
                </button>
            </div>
            <div className="space-y-3">
                {data?.apis.map((api, i) => (
                    <div key={i} className={`rounded-lg border p-4 ${api.status === 'online' ? 'border-green-500/20 bg-green-500/5' : api.status === 'offline' ? 'border-red-500/20 bg-red-500/5' : 'border-yellow-500/20 bg-yellow-500/5'}`}>
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-center gap-3">
                                {api.name.includes('TibiaData') ? <Database className="w-5 h-5 text-blue-400" /> :
                                    api.name.includes('Wiki') || api.name.includes('Fandom') ? <BookOpen className="w-5 h-5 text-purple-400" /> :
                                        <Globe className="w-5 h-5 text-amber-400" />}
                                <div>
                                    <div className="font-medium text-slate-100">{api.name}</div>
                                    <div className="text-xs text-slate-500 font-mono">{api.url}</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                                {getStatusIcon(api.status)}
                                {api.latency_ms !== undefined && <span className="text-xs text-slate-500">{api.latency_ms}ms</span>}
                                {api.status_code && <span className="text-xs text-slate-500">HTTP {api.status_code}</span>}
                            </div>
                        </div>
                        {api.error && <div className="mt-2 text-xs text-red-300 bg-red-900/20 rounded px-2 py-1">{api.error}</div>}
                        {api.full_response && (
                            <div className="mt-2">
                                <button onClick={() => setExpandedAPI(expandedAPI === api.name ? null : api.name)} className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1">
                                    <Code className="w-3.5 h-3.5" /> {expandedAPI === api.name ? 'Hide' : 'Show'} full response
                                </button>
                                {expandedAPI === api.name && (
                                    <pre className="mt-2 text-xs text-green-400 bg-slate-950 rounded p-3 overflow-x-auto max-h-64 overflow-y-auto">
                                        {JSON.stringify(api.full_response, null, 2)}
                                    </pre>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Database Sync tab ──────────────────────────────────────────────────────────
function DBSyncTab() {
    const toast = useToast();
    const [loading, setLoading] = useState(false);
    const [preview, setPreview] = useState<SyncPreview | null>(null);
    const [selectedChanges, setSelectedChanges] = useState<number[]>([]);

    const handlePreview = async () => {
        setLoading(true);
        try {
            const response = await axios.post<SyncPreview>(`${API_BASE}/sync/preview`, {}, { headers: authHeader() });
            setPreview(response.data);
            setSelectedChanges([]);
            toast.success('Preview loaded');
        } catch {
            toast.error('Failed to preview changes');
        } finally {
            setLoading(false);
        }
    };

    const handleApprove = async (approveAll: boolean) => {
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/sync/approve`, {}, {
                params: { approve_all: approveAll, change_indices: approveAll ? undefined : selectedChanges },
                headers: authHeader(),
            });
            toast.success('Changes approved and applied');
            setPreview(null);
            setSelectedChanges([]);
        } catch {
            toast.error('Failed to apply changes');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3">
                <button
                    onClick={handlePreview}
                    disabled={loading}
                    className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
                    Preview Changes
                </button>
                {preview && preview.changes.length > 0 && (
                    <>
                        <button
                            onClick={() => void handleApprove(false)}
                            disabled={loading || selectedChanges.length === 0}
                            className="flex items-center gap-2 rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                        >
                            <Download className="w-4 h-4" /> Apply Selected ({selectedChanges.length})
                        </button>
                        <button
                            onClick={() => void handleApprove(true)}
                            disabled={loading}
                            className="flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                        >
                            <CheckCircle className="w-4 h-4" /> Apply All
                        </button>
                    </>
                )}
            </div>

            {preview && (
                <div className="space-y-3">
                    <div className="flex gap-4 text-sm text-slate-400">
                        <span><span className="text-slate-200 font-medium">{preview.total_changes}</span> changes</span>
                        <span><span className="text-amber-400 font-medium">{preview.pending_approvals}</span> need approval</span>
                        {preview.backup_created && <span className="text-green-400">✓ Backup created</span>}
                    </div>
                    {preview.changes.length === 0 ? (
                        <div className="text-center py-8 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700">No pending changes.</div>
                    ) : (
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-slate-950/50">
                                        <tr>
                                            <th className="p-3 text-left"><input type="checkbox" onChange={(e) => setSelectedChanges(e.target.checked ? preview.changes.map((_, i) => i) : [])} checked={selectedChanges.length === preview.changes.length} /></th>
                                            <th className="p-3 text-left text-xs uppercase text-slate-400">Entity</th>
                                            <th className="p-3 text-left text-xs uppercase text-slate-400">Action</th>
                                            <th className="p-3 text-left text-xs uppercase text-slate-400">Source</th>
                                            <th className="p-3 text-left text-xs uppercase text-slate-400">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {preview.changes.map((change, i) => (
                                            <tr key={i} className="border-t border-slate-800">
                                                <td className="p-3"><input type="checkbox" checked={selectedChanges.includes(i)} onChange={() => setSelectedChanges((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i])} /></td>
                                                <td className="p-3 text-sm text-slate-200">{change.entity}</td>
                                                <td className="p-3 text-sm text-slate-300">{change.action}</td>
                                                <td className="p-3 text-xs text-slate-400">{change.source_api}</td>
                                                <td className="p-3 text-xs">
                                                    <span className={`px-2 py-1 rounded ${change.approval_required ? 'bg-amber-900/40 text-amber-300' : 'bg-slate-800 text-slate-400'}`}>
                                                        {change.status}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Admin Sync tab ─────────────────────────────────────────────────────────────
const SYNC_APIS = [
    { name: 'creatures', icon: '🐉', label: 'Creatures', description: 'Sync beasts and monsters' },
    { name: 'items', icon: '⚔️', label: 'Items', description: 'Sync weapons, armors and objects' },
    { name: 'hunting-places', icon: '🗺️', label: 'Hunt Zones', description: 'Sync hunting locations' },
    { name: 'quests', icon: '📜', label: 'Quests', description: 'Sync missions and rewards' },
];

function AdminSyncTab() {
    const toast = useToast();
    const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
    const [stats, setStats] = useState<SyncStats | null>(null);
    const [loading, setLoading] = useState(false);
    const [syncingApis, setSyncingApis] = useState<Set<string>>(new Set());

    const loadData = async () => {
        setLoading(true);
        try {
            const [logsRes, statsRes] = await Promise.allSettled([
                axios.get<SyncLog[]>(`${API_BASE}/admin/sync/bestiary/logs?limit=20`, { headers: authHeader() }),
                axios.get<SyncStats>(`${API_BASE}/admin/sync/bestiary/stats`, { headers: authHeader() }),
            ]);
            if (logsRes.status === 'fulfilled') setSyncLogs(logsRes.value.data);
            if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
        } catch { /* ignore */ }
        finally { setLoading(false); }
    };

    useEffect(() => { void loadData(); }, []);

    const triggerSync = async (apiName: string) => {
        setSyncingApis((prev) => new Set([...prev, apiName]));
        try {
            await axios.post(
                `${API_BASE}/admin/sync/bestiary/start?source=${apiName}&mode=auto`,
                {},
                { headers: authHeader() }
            );
            toast.success(`Sync started for ${apiName}`);
            setTimeout(() => void loadData(), 3000);
        } catch (error: any) {
            toast.error(error.response?.data?.detail || `Failed to start sync for ${apiName}`);
        } finally {
            setSyncingApis((prev) => { const n = new Set(prev); n.delete(apiName); return n; });
        }
    };

    return (
        <div className="space-y-6">
            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                        { label: 'Creatures', value: stats.creatures },
                        { label: 'Items', value: stats.items },
                        { label: 'Hunt Zones', value: stats.hunting_places },
                        { label: 'Quests', value: stats.quests },
                    ].map(({ label, value }) => (
                        <div key={label} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-slate-100">{value.toLocaleString()}</div>
                            <div className="text-xs text-slate-400 mt-1">{label}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Sync triggers */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {SYNC_APIS.map(({ name, icon, label, description }) => {
                    const busy = syncingApis.has(name);
                    return (
                        <button
                            key={name}
                            onClick={() => void triggerSync(name)}
                            disabled={busy}
                            className="flex flex-col items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-center hover:border-amber-500/50 hover:bg-amber-500/5 transition-colors disabled:opacity-50"
                        >
                            <span className="text-2xl">{icon}</span>
                            <span className="text-sm font-medium text-slate-100">{label}</span>
                            <span className="text-xs text-slate-500">{description}</span>
                            {busy && <Loader2 className="w-4 h-4 animate-spin text-amber-400" />}
                        </button>
                    );
                })}
            </div>

            {/* Logs */}
            <div>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                        <Clock className="w-4 h-4 text-slate-400" /> Recent sync logs
                    </h3>
                    <button onClick={loadData} disabled={loading} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 rounded px-2 py-1">
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </button>
                </div>
                {syncLogs.length === 0 ? (
                    <div className="text-center py-8 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700">No sync logs yet.</div>
                ) : (
                    <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-950/50">
                                <tr>
                                    <th className="p-3 text-left text-xs uppercase text-slate-400">API</th>
                                    <th className="p-3 text-left text-xs uppercase text-slate-400">Status</th>
                                    <th className="p-3 text-left text-xs uppercase text-slate-400">Items</th>
                                    <th className="p-3 text-left text-xs uppercase text-slate-400">Errors</th>
                                    <th className="p-3 text-left text-xs uppercase text-slate-400">Started</th>
                                </tr>
                            </thead>
                            <tbody>
                                {syncLogs.map((log) => (
                                    <tr key={log.id} className="border-t border-slate-800">
                                        <td className="p-3 text-slate-200">{log.api_name}</td>
                                        <td className="p-3">
                                            <span className="flex items-center gap-1">
                                                {getStatusIcon(log.status)}
                                                <span className={`text-xs ${log.status === 'success' ? 'text-green-400' : log.status === 'error' ? 'text-red-400' : 'text-slate-400'}`}>
                                                    {log.status}
                                                </span>
                                            </span>
                                        </td>
                                        <td className="p-3 text-slate-300">{log.processed_items}{log.total_items ? `/${log.total_items}` : ''}</td>
                                        <td className="p-3">
                                            {log.error_count > 0
                                                ? <span className="text-red-400">{log.error_count}</span>
                                                : <span className="text-slate-600">0</span>
                                            }
                                        </td>
                                        <td className="p-3 text-slate-500 text-xs">{new Date(log.started_at).toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

// ── Main DataTools component ───────────────────────────────────────────────────
export default function DataTools() {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState<Tab>('api-monitor');

    const tabs: { id: Tab; label: string; icon: any; description: string }[] = [
        { id: 'api-monitor', label: 'API Monitor', icon: Globe, description: 'External API health checks' },
        { id: 'db-sync', label: 'Database Sync', icon: GitBranch, description: 'Preview and apply DB changes' },
        { id: 'admin-sync', label: 'Data Sync', icon: RefreshCw, description: 'Trigger bestiary syncs' },
        { id: 'knowledge', label: t('knowledgeOps.navigation'), icon: Workflow, description: t('knowledgeOps.subtitle') },
    ];

    return (
        <div className="space-y-4">
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-1">
                    <Database className="w-5 h-5 text-amber-500" />
                    <h1 className="text-xl font-semibold text-slate-100">Data Tools</h1>
                </div>
                <p className="text-sm text-slate-400">API monitoring, database sync previews, and bestiary data updates — all in one place.</p>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-slate-700">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center gap-2 px-4 py-2.5 border-b-2 text-sm font-medium transition-colors ${
                            activeTab === id
                                ? 'border-amber-500 text-amber-400'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Tab content */}
            <div>
                {activeTab === 'api-monitor' && <APIMonitorTab />}
                {activeTab === 'db-sync' && <DBSyncTab />}
                {activeTab === 'admin-sync' && <AdminSyncTab />}
                {activeTab === 'knowledge' && <KnowledgeOperations />}
            </div>
        </div>
    );
}
